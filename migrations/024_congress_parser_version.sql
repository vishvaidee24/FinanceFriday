BEGIN;

ALTER TABLE ownership.congress_filing
    ADD COLUMN IF NOT EXISTS parser_version TEXT;

COMMENT ON COLUMN ownership.congress_filing.parser_version IS
    'Parser/universe version last used to inspect this filing.';

COMMIT;
