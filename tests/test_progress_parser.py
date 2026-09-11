from app.core.progress_parser import ProgressParser


def test_progress_parser_computes_percent_and_eta():
    parser = ProgressParser(total_duration_seconds=100.0)
    lines = [
        "frame=100",
        "fps=25.0",
        "out_time_us=50000000",  # 50 seconds
        "total_size=1000000",
        "speed=2.0x",
        "progress=continue",
    ]
    state = None
    for line in lines:
        state = parser.feed(line) or state
    assert state is not None
    assert state.out_time_seconds == 50.0
    assert state.percent == 50.0
    assert state.speed == 2.0
    assert state.eta_seconds == 25.0  # 50 seconds remaining / 2.0x speed


def test_progress_parser_handles_unknown_duration():
    parser = ProgressParser(total_duration_seconds=None)
    parser.feed("out_time_us=10000000")
    state = parser.feed("progress=continue")
    assert state.percent is None
    assert state.out_time_seconds == 10.0


def test_progress_parser_ignores_blank_and_malformed_lines():
    parser = ProgressParser(total_duration_seconds=10.0)
    assert parser.feed("") is None
    assert parser.feed("not a key value line") is None
