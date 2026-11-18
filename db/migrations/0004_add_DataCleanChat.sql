-- CreateTable: DataCleanChat — stateful AI data-cleaning session.
-- Mirrors VirtualDatasetChat, minus currentStage (no staged conversation machine).
-- datasetId → UserDataset ON DELETE CASCADE: deleting a dataset removes its chats.
CREATE TABLE "DataCleanChat" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "datasetId" TEXT,
    "contextData" JSONB NOT NULL DEFAULT '{}'::jsonb,
    "messages" JSONB NOT NULL DEFAULT '[]'::jsonb,
    "status" TEXT NOT NULL DEFAULT 'active',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "DataCleanChat_pkey" PRIMARY KEY ("id")
);

ALTER TABLE "DataCleanChat"
    ADD CONSTRAINT "DataCleanChat_userId_fkey"
    FOREIGN KEY ("userId") REFERENCES "User"("id")
    ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "DataCleanChat"
    ADD CONSTRAINT "DataCleanChat_datasetId_fkey"
    FOREIGN KEY ("datasetId") REFERENCES "UserDataset"("id")
    ON DELETE CASCADE ON UPDATE CASCADE;

CREATE INDEX "DataCleanChat_userId_idx" ON "DataCleanChat" ("userId");
CREATE INDEX "DataCleanChat_datasetId_idx" ON "DataCleanChat" ("datasetId");
CREATE INDEX "DataCleanChat_status_idx" ON "DataCleanChat" ("status");
