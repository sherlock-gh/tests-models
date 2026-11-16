# Contract: Desktop local HTTP/JSON API

Server binds to `127.0.0.1` only. Requests/responses are JSON. Success: 2xx with the resource. Failure: 4xx with `{"error": {"code", "message"}}` (see [operations.md](operations.md)); the server never exits on a request error (unexpected exceptions return 500 with a message and leave data unchanged).

| Method & path | Operation |
|---|---|
| GET/POST `/api/cleaners`, GET/PUT/DELETE `/api/cleaners/{id}` | cleaner CRUD |
| GET/POST `/api/clients`, GET/PUT/DELETE `/api/clients/{id}` | client CRUD |
| GET/POST `/api/jobs`, GET/PUT/DELETE `/api/jobs/{id}` | job CRUD (POST = bookJob) |
| POST `/api/jobs/{id}/arrive`, `/depart`, `/extend` | field operations (back-office correction/testing) |
| GET `/api/cleaners/{id}/day?date=YYYY-MM-DD` | cleaner day view |
| GET `/api/invoices?settled=true\|false`, GET `/api/invoices/{id}` | invoices |
| POST `/api/invoices/{id}/pay` body `{"amountCents"}` | payment |
| GET `/api/utilization?date=YYYY-MM-DD` | per-cleaner day/week utilization |
| GET `/` | the single-page back-office UI |

The mobile Swift package exposes the same operations as `CleaningService` methods that `throw` a `CleaningError` carrying the same codes; it has no UI and no server.
