from __future__ import annotations

from tools.cli import scan


def _parse_and_apply(argv: list[str]):
    parser = scan.build_parser()
    args = parser.parse_args(argv)
    return scan.apply_scan_defaults(args, argv)


def test_apply_scan_defaults_no_stage_flags_enables_full_pipeline():
    args = _parse_and_apply(["--user", "@TestUser"])

    for attr in scan.FULL_PIPELINE_STAGE_ATTRS:
        assert getattr(args, attr) is True


def test_apply_scan_defaults_with_explicit_stage_flag_does_not_auto_enable_other_stages():
    args = _parse_and_apply(["--user", "@TestUser", "--ingest-positions"])

    assert args.ingest_positions is True
    for attr in scan.FULL_PIPELINE_STAGE_ATTRS:
        if attr == "ingest_positions":
            continue
        assert getattr(args, attr) is None


def test_apply_scan_defaults_full_overrides_explicit_stage_flags():
    args = _parse_and_apply(["--user", "@TestUser", "--ingest-positions", "--full"])

    for attr in scan.FULL_PIPELINE_STAGE_ATTRS:
        assert getattr(args, attr) is True


def test_apply_scan_defaults_lite_sets_minimal_profile_only():
    args = _parse_and_apply(["--user", "@TestUser", "--lite"])

    for attr in scan.LITE_PIPELINE_STAGE_ATTRS:
        assert getattr(args, attr) is True
    for attr in scan.FULL_PIPELINE_STAGE_ATTRS:
        if attr in scan.LITE_PIPELINE_STAGE_SET:
            continue
        assert getattr(args, attr) is False
