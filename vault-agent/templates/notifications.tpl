{{ with secret "secret/data/notifications" -}}
{
  "notifications_api_key": "{{ .Data.data.api_key }}"
}
{{- end }}