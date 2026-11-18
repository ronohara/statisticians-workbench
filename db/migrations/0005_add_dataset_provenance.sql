-- Add provenance columns to UserDataset.
--   sourceOrigin      — the ORIGINAL source type of a derived (cleaned) dataset
--                       (virtual / upload / notebook / postgresql / mysql / mssql / access).
--                       NULL for genuine (non-derived) datasets.
--   sourceDatasetId   — the immediate parent dataset id (lineage). NULL for genuine datasets.
--
-- sourceDatasetId is a SOFT lineage pointer, not a containment edge, so it is
-- ON DELETE SET NULL: a cleaned copy is an independent, materialised snapshot and
-- must survive the deletion of its source. sourceOrigin (a plain string) preserves
-- the filter group and the "is this cleaned?" marker after the parent is gone.
ALTER TABLE "UserDataset" ADD COLUMN "sourceOrigin" TEXT;
ALTER TABLE "UserDataset" ADD COLUMN "sourceDatasetId" TEXT;

ALTER TABLE "UserDataset"
    ADD CONSTRAINT "UserDataset_sourceDatasetId_fkey"
    FOREIGN KEY ("sourceDatasetId") REFERENCES "UserDataset"("id")
    ON DELETE SET NULL ON UPDATE CASCADE;

CREATE INDEX "UserDataset_sourceDatasetId_idx" ON "UserDataset" ("sourceDatasetId");
