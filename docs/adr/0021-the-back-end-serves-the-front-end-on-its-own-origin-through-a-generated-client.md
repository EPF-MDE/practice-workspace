# The back end serves the front end on its own origin, through a client generated from its API

A Student's session is a cookie the back end sets, and the front end calls the back end's API on every screen. **So the front end is served from the same origin as the API, and calls it through a client generated from the back end's OpenAPI schema.**

- The build goes to `frontend/dist/`. The back end serves it on the same domain (`_serve_frontend` in `backend/app/main.py`), from `backend/static` where an artefact puts it, else from `frontend/dist` locally (`STATIC_CANDIDATES`); any path but `/api` and `/auth` gets `index.html`.
- In development, Vite proxies `/api` and `/auth` to the back end on `:8000` (`frontend/vite.config.ts`).
- The session cookie stays first-party, and `client.setConfig({ baseURL: "", withCredentials: true })` in `frontend/src/main.tsx` sends it with every request, with no CORS to configure.
- The front end's `generate-client` script writes the schema with `backend/scripts/openapi.py`, then generates the client into `frontend/src/client/`. The generator names each service and method from the operation id, so `create_app` in `backend/app/main.py` sets each route's operation id to `<tag>-<function>` (`generate_unique_id_function`), which gives names such as `SessionService.me()`.
- Changing how operation ids are built renames every method of the generated client.
