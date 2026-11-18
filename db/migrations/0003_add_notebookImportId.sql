-- AlterTable: add notebookImportId to UserDataset (links a dataset back to its NotebookImport).
-- A foreign key with ON DELETE CASCADE enforces referential integrity at the DB level:
-- deleting a NotebookImport removes its linked UserDataset rows automatically.
ALTER TABLE "UserDataset" ADD COLUMN "notebookImportId" TEXT;

ALTER TABLE "UserDataset"
    ADD CONSTRAINT "UserDataset_notebookImportId_fkey"
    FOREIGN KEY ("notebookImportId") REFERENCES "NotebookImport"("id")
    ON DELETE CASCADE ON UPDATE CASCADE;

-- Index on the FK column so the cascade lookup does not full-scan UserDataset.
CREATE INDEX "UserDataset_notebookImportId_idx" ON "UserDataset" ("notebookImportId");
