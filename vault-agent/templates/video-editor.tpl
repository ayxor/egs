{{ with secret "secret/data/video-editor" -}}
{
  "video_editor_api_key": "{{ .Data.data.api_key }}",
  "object_storage_api_key": "{{ (secret "secret/data/object-storage").Data.data.api_key }}"
}
{{- end }}