{{ with secret "secret/data/object-storage" -}}
{"api_key":"{{ .Data.data.api_key }}"}
{{- end }}
