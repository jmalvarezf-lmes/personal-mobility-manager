import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import SwaggerUI from "swagger-ui-react";
import "swagger-ui-react/swagger-ui.css";
import { injectApiServer } from "../api/openapi";
import Nav from "../components/Nav";

export default function ApiDocsPage() {
  const { t } = useTranslation();
  const [spec, setSpec] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const response = await fetch("/api/openapi.json");
        if (!response.ok) {
          throw new Error(`Unexpected response from /api/openapi.json: ${response.status}`);
        }
        const rawSpec = (await response.json()) as Record<string, unknown>;
        setSpec(injectApiServer(rawSpec));
      } catch (err) {
        setError(err instanceof Error ? err.message : t("page.apiDocs.loadError"));
      }
    }
    void load();
  }, [t]);

  return (
    <div className="min-h-screen bg-gray-50">
      <Nav />
      <main className="p-6">
        <h1 className="mb-4 text-2xl font-bold text-gray-800">{t("page.apiDocs.title")}</h1>

        {error && (
          <p role="alert" className="mb-4 text-red-600">
            {error}
          </p>
        )}

        {!spec && !error && <p className="text-gray-500">{t("page.apiDocs.loading")}</p>}

        {spec && <SwaggerUI spec={spec} />}
      </main>
    </div>
  );
}
