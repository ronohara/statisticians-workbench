-- AlterTable: add isShared Boolean to shareable resource models
ALTER TABLE "UserDataset" ADD COLUMN "isShared" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "UserDatabaseConnection" ADD COLUMN "isShared" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "UserAIConnection" ADD COLUMN "isShared" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "Recipe" ADD COLUMN "isShared" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "NotebookImport" ADD COLUMN "isShared" BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE "DataPreparationRule" ADD COLUMN "isShared" BOOLEAN NOT NULL DEFAULT false;

-- Data migration: set isShared=true for existing records where group != '00'
-- (these were explicitly shared under the old model)
UPDATE "UserDataset" SET "isShared" = true WHERE "datasetGroup" != '00';
UPDATE "UserDatabaseConnection" SET "isShared" = true WHERE "dbConnectionGroup" != '00';
UPDATE "UserAIConnection" SET "isShared" = true WHERE "aiConnectionGroup" != '00';
UPDATE "Recipe" SET "isShared" = true WHERE "recipeGroup" != '00';
UPDATE "NotebookImport" SET "isShared" = true WHERE "notebookGroup" != '00';
UPDATE "DataPreparationRule" SET "isShared" = true WHERE "ruleGroup" != '00';
