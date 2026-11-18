-- Add referential integrity for VisualizationInstance.visualizationTypeId → VisualizationType.id.
-- Quirk: the column was a bare Int with no relation, so the DELETE handler enforced
-- "in use" manually (count → 409). The FK (RESTRICT) moves that to the DB and closes
-- the count-then-delete race. ON UPDATE CASCADE matches the existing userId FK.
ALTER TABLE "VisualizationInstance"
    ADD CONSTRAINT "VisualizationInstance_visualizationTypeId_fkey"
    FOREIGN KEY ("visualizationTypeId") REFERENCES "VisualizationType"("id")
    ON UPDATE CASCADE ON DELETE RESTRICT;
