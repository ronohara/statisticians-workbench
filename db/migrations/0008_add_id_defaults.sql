-- Give every cuid-based Prisma "id" column a DB-level default so raw-SQL INSERTs
-- that omit "id" no longer fail with NotNullViolation (quirk: @default(cuid()) was
-- application-layer only — no DEFAULT clause in the DB). Python already writes
-- uuid4() explicitly, so this is a pure safety net; existing explicit ids still
-- override the default. gen_random_uuid() emits a canonical UUID (cast to text on
-- assignment), matching the uuid4 shape the backend already produces.
ALTER TABLE "AIRecipeSession"       ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "Account"               ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "DataCleanChat"         ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "DataPreparationRule"   ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "DatasetDescription"    ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "NotebookImport"        ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "PasswordResetToken"    ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "Recipe"                ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "RecipeExecution"       ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "RecipePreparationRule" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "Session"               ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "User"                  ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "UserDataset"           ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "UserGroup"             ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "VerificationToken"     ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
ALTER TABLE "VirtualDatasetChat"    ALTER COLUMN "id" SET DEFAULT gen_random_uuid();
