-- Add username labeling and artifact path columns to dossier exports

ALTER TABLE polytool.user_dossier_exports
    ADD COLUMN IF NOT EXISTS username String;

ALTER TABLE polytool.user_dossier_exports
    ADD COLUMN IF NOT EXISTS username_slug String;

ALTER TABLE polytool.user_dossier_exports
    ADD COLUMN IF NOT EXISTS artifact_path String;
