/**
 * Injects (overwriting any existing entry) a same-origin `servers` entry
 * into a raw OpenAPI document, so Swagger UI resolves "Try it out" requests
 * through the app's existing `/api` same-origin proxy instead of the bare
 * operation paths FastAPI generates.
 */
export function injectApiServer(spec: Record<string, unknown>): Record<string, unknown> {
  spec.servers = [{ url: "/api" }];
  return spec;
}
