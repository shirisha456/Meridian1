{{/*
Unlike core-api's fixed name, this chart is installed once per worker
service with its own values-*.yaml override — nameOverride gives each
installation its own resource names.
*/}}
{{- define "worker.name" -}}
{{ .Values.nameOverride | default .Chart.Name }}
{{- end }}

{{- define "worker.labels" -}}
app.kubernetes.io/name: {{ include "worker.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "worker.selectorLabels" -}}
app.kubernetes.io/name: {{ include "worker.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
