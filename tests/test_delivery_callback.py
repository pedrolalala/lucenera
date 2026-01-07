import unittest

import main


class FakeInsertExecutor:
    def __init__(self, table_name, storage):
        self.table_name = table_name
        self.storage = storage
        self._payload = None

    def insert(self, payload):
        self._payload = payload
        return self

    def execute(self):
        entry = {"table": self.table_name, "payload": self._payload}
        self.storage.append(entry)
        return type("Response", (), {"data": [self._payload]})


class FakeSupabase:
    def __init__(self):
        self.storage = []
        self.last_table = None

    def table(self, name):
        self.last_table = name
        return FakeInsertExecutor(name, self.storage)


class DeliveryCallbackTestCase(unittest.TestCase):
    def setUp(self):
        self.original_supabase = main.supabase
        self.fake_supabase = FakeSupabase()
        main.supabase = self.fake_supabase

    def tearDown(self):
        main.supabase = self.original_supabase

    def test_delivery_callback_processing(self):
        payload = {
            "phone": "5516999999999",
            "messageId": "ABC123",
            "error": "Phone number does not exist",
            "instanceId": "INSTANCE-1",
            "zaapId": "ZAAP-XYZ",
            "momment": 1764104202021,
            "type": "DeliveryCallback",
            "_traceContext": {"traceId": "trace", "spanId": "span"},
        }

        self.assertTrue(main._is_message_event(payload))

        parsed = main.parse_zapi_payload(payload)
        saved_row = main._save_delivery_callback(payload, parsed=parsed)

        self.assertIsNotNone(saved_row)
        self.assertEqual(self.fake_supabase.last_table, main.DELIVERY_CALLBACKS_TABLE)
        self.assertEqual(len(self.fake_supabase.storage), 1)
        inserted_payload = self.fake_supabase.storage[0]["payload"]
        self.assertEqual(inserted_payload["kind"], "CALLBACK")
        self.assertEqual(inserted_payload["message_id"], "ABC123")
        self.assertEqual(inserted_payload["status"], "Phone number does not exist")
        self.assertEqual(inserted_payload["phone"], "5516999999999")
        self.assertIn("raw_json", inserted_payload)
        self.assertIn("updated_at", inserted_payload)


if __name__ == "__main__":
    unittest.main()
