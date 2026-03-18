# Video Editor Service

Servico interno de processamento assincrono de media.

O Video Editor recebe um recurso por URL, aplica operacoes, e escreve o resultado
noutra URL. O servico e agnostico ao negocio da plataforma e autenticado por API key.

## Contrato da API

O contrato oficial esta documentado em `video-editor.yaml` (OpenAPI 3.0.3).
Este README resume o mesmo contrato para consulta rapida.

Base URL (local): `http://localhost:8080`

Header obrigatorio em todos os endpoints:

```http
X-API-Key: <key>
```

## Endpoints

| Metodo | Path | Descricao |
|---|---|---|
| POST | /jobs | Criar job com id gerado pelo servico |
| PUT | /jobs/{job_id} | Criar/substituir job com id fixo (idempotencia) |
| DELETE | /jobs/{job_id} | Cancelar job |
| GET | /jobs/{job_id} | Obter estado e progresso do job |
| GET | /jobs/{job_id}/progress | Stream SSE de progresso |
| GET | /jobs/{job_id}/operations | Operacoes pedidas para o job |
| GET | /jobs/operations | Operacoes suportadas por esta instancia |

## Modelo de request

### POST /jobs e PUT /jobs/{job_id}

```json
{
	"src_url": "https://storage/raw/abc123.mp4",
	"dst_url": "https://storage/processed/abc123.mp4",
	"progress_url": "https://composer/internal/jobs/progress",
	"operations": [
		{
			"type": "watermark",
			"params": {
				"text": "UA",
				"position": "bottom-right",
				"opacity": 0.8
			}
		}
	]
}
```

Campos obrigatorios:

- src_url
- dst_url
- operations (lista nao vazia)

## Estado do job

Resposta de GET /jobs/{job_id}:

```json
{
	"job_id": "job_7f3a1b",
	"status": "processing",
	"percent": 45,
	"created_at": "2026-03-17T10:00:00Z",
	"updated_at": "2026-03-17T10:01:23Z"
}
```

Estados possiveis:

- queued
- processing
- done
- failed
- cancelled

## Codigos HTTP esperados

- 200 OK: leitura com sucesso
- 202 Accepted: job aceite para processamento assincrono
- 204 No Content: cancelamento aceite
- 400 Bad Request: payload invalido ou campos em falta
- 401 Unauthorized: API key invalida ou em falta
- 404 Not Found: job inexistente
- 422 Unprocessable Entity: operacao desconhecida/nao suportada

## Notas de design

- O servico gere jobs de processamento e nao ownership de ficheiros de video.
- Por isso, nao existe CRUD de `/videos` neste microservico.
- `POST /jobs` cria novo job com id gerado pelo servico.
- `PUT /jobs/{job_id}` permite retries idempotentes com id controlado pelo caller.
- `DELETE /jobs/{job_id}` cancela jobs queued/processing.

## Como correr

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

API key custom (opcional):

```bash
export VIDEO_EDITOR_API_KEY="my-key"
python3 app.py
```

## Como testar

```bash
chmod +x test.sh
./test.sh
```

Se estiver tudo correto, o script termina com:

```text
All tests passed.
```

