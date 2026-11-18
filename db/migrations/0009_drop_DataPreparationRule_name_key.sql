-- Drop the (datasetId, name) unique index: the app treats rule name as decorative
-- and de-duplicates on content_hash(operations) instead, so name-uniqueness is not
-- the intended semantics. The content-hash dedup is the real uniqueness mechanism,
-- and the unique index was over-constraining (duplicate name + different operations
-- produced a raw 500). (item 6 unique-index audit.)
DROP INDEX IF EXISTS "DataPreparationRule_datasetId_name_key";
