"""The lease tab: a run takes, checks and releases its line; the pin is read
and written; every whole-block op is guarded."""

import unittest

from hypo import lease

EMPTY = ("<doc node='n' rev='4' sinceRev='0'><paragraph id='s1.0' h='aa' heading='1'>"
         "<text id='.1'>lease</text></paragraph>"
         "<paragraph id='.6' h='bb' heading='2'><text id='.7'>Leases</text></paragraph>"
         "<paragraph id='.15' h='cc'><text id='.16'>None held.</text></paragraph>"
         "<paragraph id='.30' h='dd' heading='2'><text id='.31'>Tooling</text></paragraph>"
         "<paragraph id='.40' h='ee'><text id='.41'>None yet.</text></paragraph></doc>")


def held(*lines, rev=6):
    items = "".join("<listItem id='.%d' h='i%d'><paragraph id='.%d' h='p%d'><text id='.%d'>%s"
                    "</text></paragraph></listItem>" % (100 + 10 * i, i, 101 + 10 * i, i,
                                                        102 + 10 * i, line)
                    for i, line in enumerate(lines))
    return ("<doc node='n' rev='%d' sinceRev='0'><paragraph id='s1.0' h='aa' heading='1'>"
            "<text id='.1'>lease</text></paragraph>"
            "<paragraph id='.6' h='bb' heading='2'><text id='.7'>Leases</text></paragraph>"
            "<list id='.99' h='ll' kind='bullet'>%s</list>"
            "<paragraph id='.300' h='dd' heading='2'><text id='.301'>Tooling</text></paragraph>"
            "<paragraph id='.310' h='ee'><text id='.311'>principal plugin abc1234, last written "
            "2026-10-22 by s-old.</text></paragraph></doc>" % (rev, items))


A = lease.line("canondb", "s-a", "/principal:dictate", "2026-10-22T10:00Z")
B = lease.line("ordo", "s-b", "/principal:ask", "2026-10-22T10:01Z")
ALL = lease.line("all", "s-c", "/principal:bootstrap", "2026-10-22T10:02Z")


class TakeTest(unittest.TestCase):
    def test_the_first_line_replaces_none_held_guarded(self):
        ops = lease.take(EMPTY, "canondb", "s-a", "/principal:dictate", "2026-10-22T10:00Z")
        self.assertEqual(len(ops), 1)
        op = ops[0]
        self.assertEqual(op["op"], "replace")
        self.assertEqual(op["target"]["ids"], ["s1.15"])
        self.assertEqual((op["ifHash"], op["ifRev"]), ("cc", 4))
        self.assertIn("canondb · s-a · /principal:dictate · since", op["with"]["from"]["content"])

    def test_a_later_line_goes_after_the_last(self):
        ops = lease.take(held(A), "ordo", "s-b", "/principal:ask", "t")
        self.assertEqual(ops[0]["op"], "insert")
        self.assertEqual(ops[0]["target"]["ids"], ["s1.100"])
        self.assertEqual(ops[0]["side"], "after")


class CheckTest(unittest.TestCase):
    def test_lines_are_read_in_order(self):
        found = lease.leases(held(A, B))
        self.assertEqual([l.session for l in found], ["s-a", "s-b"])
        self.assertEqual(found[0].scope, "canondb")

    def test_different_projects_both_hold(self):
        self.assertEqual(lease.ahead(held(A, B), "s-b"), [])

    def test_an_earlier_all_blocks_everyone(self):
        self.assertEqual([l.session for l in lease.ahead(held(ALL, B), "s-b")], ["s-c"])

    def test_a_later_all_waits_on_everyone(self):
        self.assertEqual([l.session for l in lease.ahead(held(A, B, ALL), "s-c")], ["s-a", "s-b"])

    def test_no_line_is_none(self):
        self.assertIsNone(lease.ahead(held(A), "s-z"))


class ReleaseTest(unittest.TestCase):
    def test_the_only_line_leaves_none_held(self):
        ops = lease.release(held(A), "s-a")
        self.assertEqual(ops[0]["op"], "replace")
        self.assertEqual(ops[0]["target"]["ids"], ["s1.99"])
        self.assertEqual(ops[0]["with"]["from"]["content"], lease.NONE_HELD)
        self.assertEqual((ops[0]["ifHash"], ops[0]["ifRev"]), ("ll", 6))

    def test_one_of_several_is_deleted_alone(self):
        ops = lease.release(held(A, B), "s-b")
        self.assertEqual(ops, [{"op": "delete", "target": {"kind": "blocks", "ids": ["s1.110"]},
                                "ifHash": "i1", "ifRev": 6}])

    def test_nothing_to_release(self):
        self.assertEqual(lease.release(held(A), "s-z"), [])


class OutlineTest(unittest.TestCase):
    def test_an_outline_read_is_enough_to_take(self):
        outline = ("<doc node='n' rev='3' outline='true'><paragraph id='s1.246' h='hh' heading='2'>"
                   "Leases</paragraph><paragraph id='.9959' h='nn'>None held.…</paragraph>"
                   "<paragraph id='.388' h='tt' heading='2'>Tooling</paragraph></doc>")
        ops = lease.take(outline, "all", "s-a", "/principal:bootstrap", "t")
        self.assertEqual(ops[0]["target"]["ids"], ["s1.9959"])
        self.assertEqual((ops[0]["ifHash"], ops[0]["ifRev"]), ("nn", 3))


class PinTest(unittest.TestCase):
    def test_reads_the_pin(self):
        self.assertEqual(lease.pin(held(A)), "abc1234")
        self.assertIsNone(lease.pin(EMPTY))

    def test_writes_the_pin_guarded(self):
        ops = lease.pin_ops(EMPTY, "def5678", "s-a", "2026-10-22")
        self.assertEqual(ops[0]["target"]["ids"], ["s1.40"])
        self.assertEqual((ops[0]["ifHash"], ops[0]["ifRev"]), ("ee", 4))
        self.assertEqual(lease.PIN.search(ops[0]["with"]["from"]["content"]).group(1), "def5678")


if __name__ == "__main__":
    unittest.main()
