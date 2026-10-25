import unittest
from backend.logic import next_state, TransitionError, sha256_secret, same_secret, snapshot_digest, validate_steam_id
from backend.models import RouteIn, TicketIn, VideoIn
from pydantic import ValidationError

class RulesTests(unittest.TestCase):
    def test_happy_path(self):
        state = "PREPARED"
        for action in ("commit","claim","complete"):
            state = next_state(state,action)
        self.assertEqual(state,"COMPLETE")

    def test_no_repeat_claim(self):
        with self.assertRaises(TransitionError):
            next_state("CLAIMED","claim")

    def test_no_rollback_after_commit(self):
        with self.assertRaises(TransitionError):
            next_state("READY","cancel")

    def test_cancel_only_prepared(self):
        self.assertEqual(next_state("PREPARED","cancel"),"CANCELLED")
        with self.assertRaises(TransitionError):
            next_state("COMPLETE","cancel")

    def test_secret_compare(self):
        key="some-long-secret"
        self.assertTrue(same_secret(key,sha256_secret(key)))
        self.assertFalse(same_secret("different",sha256_secret(key)))

    def test_deterministic_snapshot(self):
        self.assertEqual(snapshot_digest({"a":1,"b":2}),snapshot_digest({"b":2,"a":1}))
        self.assertNotEqual(snapshot_digest({"a":1}),snapshot_digest({"a":2}))

    def test_steam64(self):
        self.assertEqual(validate_steam_id("76561198012345678"),"76561198012345678")
        with self.assertRaises(ValueError):
            validate_steam_id("123")

    def test_ticket_quantity(self):
        with self.assertRaises(ValidationError):
            TicketIn(id="ticket",name="Invalid",classname="RPV_ticket",quantity=0)

    def test_route_loop(self):
        with self.assertRaises(ValidationError):
            RouteIn(id="route",name="No loop",source_server_id="one",target_server_id="one")

    def test_video_paths(self):
        with self.assertRaises(ValidationError):
            VideoIn(id="video",name="Unsafe",departure_asset="../../secrets.mp4")

if __name__ == "__main__":
    unittest.main()
