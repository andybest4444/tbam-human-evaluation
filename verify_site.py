#!/usr/bin/env python3
"""Compatibility entry point for the cumulative release-chain verifier."""

from verify_release_chain import main, verify

__all__ = ["main", "verify"]


if __name__ == "__main__":
    raise SystemExit(main())
