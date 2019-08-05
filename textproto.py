"""Utility methods for textproto IO."""

import logging
from typing import IO

from google.protobuf import text_format

import citylex_pb2


def read_lexicon(source: IO) -> citylex_pb2.Lexicon:
    """Reads Lexicon textproto from file handle."""
    lexicon = citylex_pb2.Lexicon()
    text_format.ParseLines(source, lexicon)
    logging.debug("Read %d entries", len(lexicon.entry))
    return lexicon


def write_lexicon(lexicon: citylex_pb2.Lexicon, sink: IO) -> None:
    """Writes lexicon textproto to file handle."""
    text_format.PrintMessage(lexicon, sink, as_utf8=True)
    logging.debug("Wrote %d entries", len(lexicon.entry))
