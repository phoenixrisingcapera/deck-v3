import { defineRailway, github, image, postgres, project, service } from "railway/iac";

export default defineRailway(() => {
  const db = postgres("Postgres");

  const api = service("Deck V3 API", {
    source: github("phoenixrisingcapera/deck-v3", { rootDirectory: "api" }),
    preDeploy: "python -m alembic upgrade heads && python -m alembic -c alembic_ai.ini upgrade heads",
    start: "python scripts/start_railway.py",
    healthcheck: "/api/health/product-ready",
    healthcheckTimeout: 300,
    restartPolicy: { type: "ON_FAILURE", maxRetries: 10 },
    env: {
      DATABASE_URL: db.env.DATABASE_URL,
    },
  });

  const frontend = service("Deck V3 Frontend", {
    source: github("phoenixrisingcapera/deck-v3", { rootDirectory: "apps/instantdeck" }),
    start: "npm start",
    healthcheck: "/",
    healthcheckTimeout: 300,
    restartPolicy: { type: "ON_FAILURE", maxRetries: 10 },
    env: {
      DECK_AISTACK_BACKEND_URL: `https://${api.env.RAILWAY_PRIVATE_DOMAIN}`,
    },
  });

  return project("Deck V3", {
    resources: [db, api, frontend],
  });
});
