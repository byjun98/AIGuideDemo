using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

[Serializable]
public class DialogueState
{
    public string character_id = "rapi";
    public int affection = 73;
    public string affection_band = "trust";
    public string[] story_flags =
    {
        "chapter_04_cleared",
        "first_advise_seen",
        "favorite_gift_received"
    };
    public string scene = "gift_received";
    public string player_recent_action = "gave_favorite_gift";
    public string time_of_day = "evening";
    public string place = "outpost_lobby";
    public string[] recent_lines = Array.Empty<string>();
    public string tone = "subculture_romantic_but_wholesome";
    public int max_spoiler_level = 1;
    public string output_language = "ko";
}

[Serializable]
public class DialogueRequest
{
    public DialogueState state = new DialogueState();
    public string query = "선물 받은 뒤 라피가 절제되게 고마워하는 대사";
    public int limit = 5;
    public float temperature = 0.7f;
    public bool accept_cache = false;
    public bool include_cards = false;
}

[Serializable]
public class DialogueOutput
{
    public string line;
    public string emotion;
    public string voice_tag;
    public string motion;
    public string risk;
}

[Serializable]
public class DialogueResponse
{
    public string generated_id;
    public string[] retrieved_card_ids;
    public DialogueOutput output;
}

public class UnityDialogueApiClient : MonoBehaviour
{
    [SerializeField] private string endpoint = "http://127.0.0.1:8000/dialogue/generate";

    public void RequestDialogue()
    {
        StartCoroutine(PostDialogue());
    }

    private IEnumerator PostDialogue()
    {
        var payload = JsonUtility.ToJson(new DialogueRequest());
        using var request = new UnityWebRequest(endpoint, "POST");
        var body = Encoding.UTF8.GetBytes(payload);
        request.uploadHandler = new UploadHandlerRaw(body);
        request.downloadHandler = new DownloadHandlerBuffer();
        request.SetRequestHeader("Content-Type", "application/json");

        yield return request.SendWebRequest();

        if (request.result != UnityWebRequest.Result.Success)
        {
            Debug.LogError(request.error + "\n" + request.downloadHandler.text);
            yield break;
        }

        var response = JsonUtility.FromJson<DialogueResponse>(request.downloadHandler.text);
        Debug.Log(response.output.line);
    }
}
