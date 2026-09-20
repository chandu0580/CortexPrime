{{- define "cg.name" -}}cortexprime-governed{{- end -}}
{{- define "cg.labels" -}}
app.kubernetes.io/name: {{ include "cg.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
{{- define "cg.sa" -}}cortexprime-governed{{- end -}}
{{- define "cg.required" -}}
{{- $_ := required "connection.tenant is required: the CortexPrime tenant that owns this connection" .Values.connection.tenant -}}
{{- $_ := required "connection.namespace is required: the namespace CortexPrime observes and may remediate" .Values.connection.namespace -}}
{{- $_ := required "database.existingSecret is required: a Secret with the PostgreSQL url" .Values.database.existingSecret -}}
{{- $_ := required "vault.address is required: the credential source (https://...)" .Values.vault.address -}}
{{- end -}}
{{- define "cg.workerUrl" -}}https://contained-{{ .worker }}-worker.{{ .ns }}.svc:8080{{- end -}}
