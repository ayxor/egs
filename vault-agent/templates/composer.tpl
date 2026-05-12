{
  "object_storage_api_key": "{{ (secret \"secret/data/object-storage\").Data.data.api_key }}",
  "video_editor_api_key": "{{ (secret \"secret/data/video-editor\").Data.data.api_key }}",
  "notifications_api_key": "{{ (secret \"secret/data/notifications\").Data.data.api_key }}"
}