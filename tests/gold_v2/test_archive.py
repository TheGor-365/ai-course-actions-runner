from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.gold_v2.archive import ArchivePolicy, inspect_archive
from scripts.gold_v2.common import RunnerError
from helpers import mark_zip_encrypted, valid_archive


class ArchiveTests(unittest.TestCase):
    def policy(self, files):
        return ArchivePolicy(expected_files=frozenset(files), receipt_schemas={"receipt.json": "fixture.receipt.v1"}, max_file_count=8, max_member_bytes=1024, max_total_bytes=4096, max_compression_ratio=20)

    def test_valid_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"ok.zip"; files, _ = valid_archive(path)
            self.assertEqual("PASS", inspect_archive(path, self.policy(files))["result"])

    def reject_modified(self, code, mutator):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"bad.zip"; files, _ = valid_archive(path); mutator(path)
            with self.assertRaisesRegex(RunnerError, code): inspect_archive(path, self.policy(files))

    def test_missing_sha256sums(self):
        def mutate(path):
            with zipfile.ZipFile(path, "w") as z: z.writestr("receipt.json", '{"schema_version":"fixture.receipt.v1"}')
        self.reject_modified("SHA256SUMS_MISSING", mutate)

    def test_extra_file(self):
        def mutate(path):
            with zipfile.ZipFile(path, "a") as z: z.writestr("extra.txt", "x")
        self.reject_modified("EXACT_FILE_SET_MISMATCH", mutate)

    def test_traversal(self):
        def mutate(path):
            with zipfile.ZipFile(path, "a") as z: z.writestr("../escape", "x")
        self.reject_modified("ARCHIVE_MEMBER_PATH_UNSAFE", mutate)

    def test_absolute_path(self):
        def mutate(path):
            with zipfile.ZipFile(path, "a") as z: z.writestr("/escape", "x")
        self.reject_modified("ARCHIVE_MEMBER_PATH_UNSAFE", mutate)

    def test_drive_path(self):
        def mutate(path):
            with zipfile.ZipFile(path, "a") as z: z.writestr("C:/escape", "x")
        self.reject_modified("ARCHIVE_MEMBER_PATH_UNSAFE", mutate)

    def test_backslash_path(self):
        def mutate(path):
            with zipfile.ZipFile(path, "a") as z: z.writestr("a\\b", "x")
        self.reject_modified("ARCHIVE_MEMBER_PATH_UNSAFE", mutate)

    def test_duplicate_entry(self):
        def mutate(path):
            with zipfile.ZipFile(path, "a") as z: z.writestr("data.txt", "duplicate")
        self.reject_modified("ARCHIVE_DUPLICATE_MEMBER", mutate)

    def test_symlink(self):
        def mutate(path):
            info=zipfile.ZipInfo("link"); info.create_system=3; info.external_attr=(stat.S_IFLNK|0o777)<<16
            with zipfile.ZipFile(path, "a") as z: z.writestr(info, "target")
        self.reject_modified("ARCHIVE_SYMLINK_FORBIDDEN", mutate)

    def test_encrypted_entry(self):
        self.reject_modified("ARCHIVE_ENCRYPTED_MEMBER_FORBIDDEN", mark_zip_encrypted)

    def test_special_file(self):
        def mutate(path):
            info=zipfile.ZipInfo("fifo"); info.create_system=3; info.external_attr=(stat.S_IFIFO|0o666)<<16
            with zipfile.ZipFile(path, "a") as z: z.writestr(info, "x")
        self.reject_modified("ARCHIVE_SPECIAL_FILE_FORBIDDEN", mutate)

    def test_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad.zip"; receipt=b'{"schema_version":"fixture.receipt.v1"}'; data=b"data\n"
            sums=(f"{'0'*64}  data.txt\n{hashlib.sha256(receipt).hexdigest()}  receipt.json\n").encode()
            with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("receipt.json",receipt); z.writestr("data.txt",data); z.writestr("SHA256SUMS",sums)
            with self.assertRaisesRegex(RunnerError,"SHA256SUMS_IDENTITY_FAILED"):
                inspect_archive(path,self.policy({"receipt.json","data.txt","SHA256SUMS"}))

    def test_receipt_schema_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad.zip"; receipt=b'{"schema_version":"wrong"}'; data=b"data\n"
            sums=(f"{hashlib.sha256(data).hexdigest()}  data.txt\n{hashlib.sha256(receipt).hexdigest()}  receipt.json\n").encode()
            with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("receipt.json",receipt); z.writestr("data.txt",data); z.writestr("SHA256SUMS",sums)
            with self.assertRaisesRegex(RunnerError,"RECEIPT_SCHEMA_MISMATCH"):
                inspect_archive(path,self.policy({"receipt.json","data.txt","SHA256SUMS"}))

    def test_member_size_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad.zip"; receipt=b'{"schema_version":"fixture.receipt.v1"}'; data=os.urandom(1100)
            sums=(f"{hashlib.sha256(data).hexdigest()}  data.txt\n{hashlib.sha256(receipt).hexdigest()}  receipt.json\n").encode()
            with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_STORED) as z:
                z.writestr("receipt.json",receipt); z.writestr("data.txt",data); z.writestr("SHA256SUMS",sums)
            with self.assertRaisesRegex(RunnerError,"ARCHIVE_MEMBER_TOO_LARGE"):
                inspect_archive(path,self.policy({"receipt.json","data.txt","SHA256SUMS"}))

    def test_total_size_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad.zip"; receipt=b'{"schema_version":"fixture.receipt.v1"}'; data=b"x"*700
            hashes={"a.bin":hashlib.sha256(data).hexdigest(),"b.bin":hashlib.sha256(data).hexdigest(),"receipt.json":hashlib.sha256(receipt).hexdigest()}
            sums="".join(f"{digest}  {name}\n" for name,digest in sorted(hashes.items())).encode()
            with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_STORED) as z:
                z.writestr("receipt.json",receipt); z.writestr("a.bin",data); z.writestr("b.bin",data); z.writestr("SHA256SUMS",sums)
            policy=ArchivePolicy(expected_files=frozenset({"receipt.json","a.bin","b.bin","SHA256SUMS"}),receipt_schemas={"receipt.json":"fixture.receipt.v1"},max_file_count=8,max_member_bytes=2048,max_total_bytes=1000,max_compression_ratio=20)
            with self.assertRaisesRegex(RunnerError,"ARCHIVE_TOTAL_TOO_LARGE"): inspect_archive(path,policy)

    def test_file_count_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad.zip"; receipt=b'{"schema_version":"fixture.receipt.v1"}'; data=b"x"
            hashes={"a":hashlib.sha256(data).hexdigest(),"b":hashlib.sha256(data).hexdigest(),"receipt.json":hashlib.sha256(receipt).hexdigest()}
            sums="".join(f"{digest}  {name}\n" for name,digest in sorted(hashes.items())).encode()
            with zipfile.ZipFile(path,"w") as z:
                z.writestr("receipt.json",receipt); z.writestr("a",data); z.writestr("b",data); z.writestr("SHA256SUMS",sums)
            policy=ArchivePolicy(expected_files=frozenset({"receipt.json","a","b","SHA256SUMS"}),receipt_schemas={"receipt.json":"fixture.receipt.v1"},max_file_count=3)
            with self.assertRaisesRegex(RunnerError,"ARCHIVE_FILE_COUNT_EXCEEDED"): inspect_archive(path,policy)

    def test_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad.zip"; files,_=valid_archive(path, secret=True)
            with self.assertRaisesRegex(RunnerError, "SENSITIVE_MARKER_FORBIDDEN"): inspect_archive(path,self.policy(files))

    def test_private_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad.zip"; files,_=valid_archive(path, private_path=True)
            with self.assertRaisesRegex(RunnerError, "PRIVATE_PAYLOAD_PATH_FORBIDDEN"): inspect_archive(path,self.policy(files))

    def test_compression_ratio(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"bad.zip"; receipt=b'{"schema_version":"fixture.receipt.v1"}'; data=b"0"*1000
            sums=(f"{hashlib.sha256(data).hexdigest()}  data.txt\n{hashlib.sha256(receipt).hexdigest()}  receipt.json\n").encode()
            with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("receipt.json",receipt); z.writestr("data.txt",data); z.writestr("SHA256SUMS",sums)
            files={"receipt.json","data.txt","SHA256SUMS"}
            with self.assertRaisesRegex(RunnerError,"COMPRESSION_RATIO_EXCEEDED"): inspect_archive(path,self.policy(files))


if __name__ == "__main__": unittest.main()
