import argparse, json, os, time
from importlib.metadata import version
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset
from transformers import (AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer,
                          TrainingArguments, TrainerCallback, set_seed)
from peft import LoraConfig, PeftModel, get_peft_model

ROOT = Path(os.environ.get("AIGD_ROOT", Path(__file__).resolve().parents[1]))


class SFTData(Dataset):
    def __init__(self, path, tok, max_len):
        self.items, dropped = [], 0
        for line in open(path, encoding="utf-8"):
            ex = json.loads(line)
            msgs = ex["messages"]
            prompt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
            p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
            a_ids = tok(msgs[-1]["content"], add_special_tokens=False)["input_ids"] + [tok.convert_tokens_to_ids("<|eot_id|>")]
            ids = p_ids + a_ids
            if len(ids) > max_len:
                dropped += 1
                continue
            self.items.append((ids, [-100] * len(p_ids) + a_ids))
        lens = [len(i) for i, _ in self.items]
        if not lens:
            raise ValueError(f"No usable samples in {path} (max_len={max_len})")
        print(f"[data] {path}: {len(self.items)} samples, dropped {dropped}, "
              f"tokens avg {sum(lens)/len(lens):.0f} max {max(lens)}")

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        ids, labels = self.items[i]
        return {"input_ids": ids, "labels": labels}


def collate(batch, pad_id):
    n = max(len(b["input_ids"]) for b in batch)
    ids = torch.full((len(batch), n), pad_id, dtype=torch.long)
    lab = torch.full((len(batch), n), -100, dtype=torch.long)
    att = torch.zeros((len(batch), n), dtype=torch.long)
    for k, b in enumerate(batch):
        L = len(b["input_ids"])
        ids[k, :L] = torch.tensor(b["input_ids"]); lab[k, :L] = torch.tensor(b["labels"]); att[k, :L] = 1
    return {"input_ids": ids, "labels": lab, "attention_mask": att}


class AnswerOnlyTrainer(Trainer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model_accepts_loss_kwargs = False

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs["labels"]
        L = labels.shape[1]
        first = int((labels != -100).float().argmax(dim=1).min().item())
        k = L - first + 1
        out = model(input_ids=inputs["input_ids"], attention_mask=inputs["attention_mask"], logits_to_keep=k)
        logits = out.logits[:, :-1, :].float()
        tgt = labels[:, -(k - 1):]
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), tgt.reshape(-1), ignore_index=-100)
        return (loss, out) if return_outputs else loss


class VramLog(TrainerCallback):
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def on_log(self, args, state, control, logs=None, **kw):
        rec = dict(step=state.global_step, time=time.time(), **(logs or {}),
                   vram_gb=round(torch.cuda.max_memory_allocated() / 2**30, 2))
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(ROOT / "models/base/kanana-1.5-2.1b-instruct-2505"))
    ap.add_argument("--train", required=True)
    ap.add_argument("--val", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--epochs", type=float, default=2)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--max-len", type=int, default=1536)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true", help="데이터 길이만 확인")
    ap.add_argument("--resume", default="", help="이어서 학습할 체크포인트 폴더 (예: .../checkpoint-300)")
    ap.add_argument("--init-adapter", default="", help="새 LoRA 대신 이미 학습한 어댑터 가중치에서 시작 (추가 학습)")
    a = ap.parse_args()
    set_seed(a.seed)

    tok = AutoTokenizer.from_pretrained(a.base)
    if tok.pad_token is None:
        tok.pad_token = "<|end_of_text|>"
    train = SFTData(a.train, tok, a.max_len)
    evald = SFTData(a.val, tok, a.max_len)
    if a.dry_run:
        return

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=torch.bfloat16)
    model = AutoModelForCausalLM.from_pretrained(a.base, quantization_config=bnb, dtype=torch.bfloat16,
                                                 device_map={"": 0}, attn_implementation="sdpa")
    model.config.use_cache = False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    if a.init_adapter:
        model = PeftModel.from_pretrained(model, a.init_adapter, is_trainable=True)
    else:
        lcfg = LoraConfig(r=a.rank, lora_alpha=a.rank * 2, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                          target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
        model = get_peft_model(model, lcfg)
    model.print_trainable_parameters()

    os.makedirs(a.out, exist_ok=True)
    log_path = ROOT / "logs/train_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    args = TrainingArguments(
        output_dir=a.out, num_train_epochs=a.epochs, per_device_train_batch_size=1,
        per_device_eval_batch_size=1, gradient_accumulation_steps=a.grad_accum, learning_rate=a.lr,
        lr_scheduler_type="cosine", warmup_ratio=0.05, logging_steps=5, eval_strategy="steps",
        eval_steps=100, save_strategy="steps", save_steps=100, save_total_limit=3, bf16=True,
        gradient_checkpointing=False, optim="paged_adamw_8bit", report_to=[], dataloader_num_workers=0,
        remove_unused_columns=False, prediction_loss_only=True,
        seed=a.seed, data_seed=a.seed, load_best_model_at_end=True,
        metric_for_best_model="eval_loss", greater_is_better=False,
    )
    tr = AnswerOnlyTrainer(model=model, args=args, train_dataset=train, eval_dataset=evald,
                 data_collator=lambda b: collate(b, tok.pad_token_id), callbacks=[VramLog(log_path)])
    t0 = time.time()
    tr.train(resume_from_checkpoint=a.resume or None)
    model.save_pretrained(a.out)
    tok.save_pretrained(a.out)
    summary = {"minutes": round((time.time() - t0) / 60, 1), "train_samples": len(train),
               "eval_samples": len(evald), "rank": a.rank, "epochs": a.epochs, "lr": a.lr,
               "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
               "final_eval": tr.evaluate()}
    summary.update(seed=a.seed, train_file=str(Path(a.train).resolve()), val_file=str(Path(a.val).resolve()),
                   init_adapter=str(Path(a.init_adapter).resolve()) if a.init_adapter else None,
                   versions={name: version(name) for name in ("torch", "transformers", "peft", "bitsandbytes")})
    (Path(a.out) / "train_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                                    encoding="utf-8")
    print(summary)


if __name__ == "__main__":
    main()
