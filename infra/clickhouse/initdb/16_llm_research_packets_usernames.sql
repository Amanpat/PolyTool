-- Add username labeling and artifact path columns to dossier exports

ALTER TABLE polyttool.user_dossier_exports
    ADD COLUMN IF NOT EXISTS username String;

ALTER TABLE polyttool.user_dossier_exports
    ADD COLUMN IF NOT EXISTS username_slug String;

ALTER TABLE polyttool.user_dossier_exports
    ADD COLUMN IF NOT EXISTS artifact_path String;
