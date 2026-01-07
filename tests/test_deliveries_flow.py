import unittest
from unittest import mock

from services import deliveries_flow
from supabase_utils import DELIVERIES_TABLE, DELIVERY_SESSIONS_TABLE


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeSelectQuery:
    def __init__(self, storage):
        self._storage = storage
        self._filters = []
        self._order_field = None
        self._order_desc = False
        self._limit_value = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, field, value):
        self._filters.append((field, value, "eq"))
        return self

    def is_(self, field, value):
        self._filters.append((field, value, "is"))
        return self

    def order(self, field, desc=False):
        self._order_field = field
        self._order_desc = bool(desc)
        return self

    def limit(self, value):
        self._limit_value = value
        return self

    def execute(self):
        rows = list(self._storage)
        for field, value, op in self._filters:
            if op == "is":
                rows = [row for row in rows if row.get(field) is value]
            else:
                rows = [row for row in rows if row.get(field) == value]
        if self._order_field:
            rows.sort(key=lambda row: row.get(self._order_field), reverse=self._order_desc)
        if self._limit_value is not None:
            rows = rows[: self._limit_value]
        return FakeResponse(rows)


class FakeInsertQuery:
    def __init__(self, storage, payload):
        self._storage = storage
        self._payload = payload

    def execute(self):
        row = dict(self._payload)
        if "id" not in row:
            row["id"] = len(self._storage) + 1
        self._storage.append(row)
        return FakeResponse([row])


class FakeUpdateQuery:
    def __init__(self, storage, payload):
        self._storage = storage
        self._payload = payload
        self._filters = []

    def eq(self, field, value):
        self._filters.append((field, value))
        return self

    def execute(self):
        updated = []
        for row in self._storage:
            if all(row.get(field) == value for field, value in self._filters):
                row.update(self._payload)
                updated.append(row)
        return FakeResponse(updated)


class FakeTable:
    def __init__(self, storage):
        self._storage = storage

    def select(self, *args, **kwargs):
        return FakeSelectQuery(self._storage).select(*args, **kwargs)

    def insert(self, payload):
        return FakeInsertQuery(self._storage, payload)

    def update(self, payload):
        return FakeUpdateQuery(self._storage, payload)


class FakeSupabase:
    def __init__(self):
        self.storage = {
            DELIVERY_SESSIONS_TABLE: [],
            DELIVERIES_TABLE: [],
        }

    def table(self, name):
        self.storage.setdefault(name, [])
        return FakeTable(self.storage[name])


class DeliveriesWizardTestCase(unittest.TestCase):
    def setUp(self):
        self.fake_supabase = FakeSupabase()
        self.teams_events = []
        self.download_patcher = mock.patch("services.deliveries_flow.download_media_bytes", autospec=True)
        self.upload_patcher = mock.patch("services.deliveries_flow.upload_to_storage", autospec=True)
        self.signed_patcher = mock.patch("services.deliveries_flow.create_signed_url", autospec=True)
        self.mock_download = self.download_patcher.start()
        self.mock_upload = self.upload_patcher.start()
        self.mock_signed = self.signed_patcher.start()
        self.mock_download.return_value = (b"fake-bytes", "image/jpeg")
        self.mock_upload.return_value = {"ok": True, "error": None, "raw": {}, "path": "25180/test.jpg"}
        self.mock_signed.return_value = "https://storage.test/signed/25180/file.jpg"

    def _latest_session(self):
        return self.fake_supabase.storage[DELIVERY_SESSIONS_TABLE][-1]

    def _capture_teams(self, event, payload):
        self.teams_events.append((event, payload))

    def tearDown(self):
        self.signed_patcher.stop()
        self.upload_patcher.stop()
        self.download_patcher.stop()

    def test_full_wizard_flow(self):
        phone = "5516992089829"

        first_payload = {
            "telefone": phone,
            "mensagem": {"text": "Entrega finalizada"},
        }
        reply = deliveries_flow.handle_event(
            first_payload,
            phone,
            raw_event=first_payload,
            supabase_client=self.fake_supabase,
            teams_notify_func=self._capture_teams,
        )
        self.assertIsNotNone(reply)
        self.assertIn("código da obra", (reply or "").lower())
        session_row = self._latest_session()
        self.assertEqual(session_row["step"], deliveries_flow.STATE_WAITING_CODE)
        self.assertEqual(session_row["entregador_phone"], phone)
        first_session_id = session_row["id"]
        self.assertEqual(len(self.fake_supabase.storage[DELIVERY_SESSIONS_TABLE]), 1)
        self.assertEqual(len(self.teams_events), 1)
        self.assertEqual(self.teams_events[0][0], "start")

        second_payload = {
            "telefone": phone,
            "mensagem": {"text": "Obra 25180"},
        }
        reply = deliveries_flow.handle_event(
            second_payload,
            phone,
            raw_event=second_payload,
            supabase_client=self.fake_supabase,
            teams_notify_func=self._capture_teams,
        )
        self.assertIsNotNone(reply)
        self.assertIn("foto", (reply or "").lower())
        session_row = self._latest_session()
        self.assertEqual(session_row["id"], first_session_id)
        self.assertEqual(session_row["step"], deliveries_flow.STATE_WAITING_PHOTO)
        self.assertEqual(session_row["obra_codigo"], "25180")

        photo_payload = {
            "telefone": phone,
            "mensagem": {"text": ""},
        }
        photo_event = {
            "phone": phone,
            "image": {"id": "media_12345"},
        }
        reply = deliveries_flow.handle_event(
            photo_payload,
            phone,
            raw_event=photo_event,
            supabase_client=self.fake_supabase,
            teams_notify_func=self._capture_teams,
        )
        self.assertIsNotNone(reply)
        self.assertIn("quem foi a pessoa", (reply or "").lower())
        session_row = self._latest_session()
        self.assertEqual(session_row["step"], deliveries_flow.STATE_WAITING_RECEIVER)
        self.assertEqual(session_row["foto_media_id"], "media_12345")
        self.assertTrue(session_row["foto_path"].startswith("25180/"))
        self.assertTrue(session_row["foto_path"].endswith(f"_{phone}.jpg"))
        self.assertEqual(session_row.get("foto_url"), "https://storage.test/signed/25180/file.jpg")
        self.mock_download.assert_called_once()
        self.mock_upload.assert_called_once()
        upload_kwargs = self.mock_upload.call_args.kwargs
        self.assertEqual(upload_kwargs["bucket"], deliveries_flow.DELIVERY_STORAGE_BUCKET)
        self.assertTrue(upload_kwargs["object_path"].startswith("25180/"))
        self.assertEqual(upload_kwargs["content_type"], "image/jpeg")
        self.assertIs(upload_kwargs["client"], self.fake_supabase)
        self.mock_signed.assert_called_once()
        signed_kwargs = self.mock_signed.call_args.kwargs
        self.assertEqual(signed_kwargs["bucket"], deliveries_flow.DELIVERY_STORAGE_BUCKET)
        self.assertTrue(signed_kwargs["object_path"].startswith("25180/"))
        self.assertEqual(signed_kwargs["expires_seconds"], deliveries_flow.SIGNED_URL_TTL_SECONDS)
        self.assertIs(signed_kwargs["client"], self.fake_supabase)

        receiver_payload = {
            "telefone": phone,
            "mensagem": {"text": "Joao Silva"},
        }
        reply = deliveries_flow.handle_event(
            receiver_payload,
            phone,
            raw_event=receiver_payload,
            supabase_client=self.fake_supabase,
            teams_notify_func=self._capture_teams,
        )
        self.assertIsNotNone(reply)
        self.assertIn("responda não", (reply or "").lower())
        session_row = self._latest_session()
        self.assertEqual(session_row["step"], deliveries_flow.STATE_WAITING_OBSERVATION)
        self.assertEqual(session_row["recebedor_nome"], "Joao Silva")

        final_payload = {
            "telefone": phone,
            "mensagem": {"text": "nao"},
        }
        reply = deliveries_flow.handle_event(
            final_payload,
            phone,
            raw_event=final_payload,
            supabase_client=self.fake_supabase,
            teams_notify_func=self._capture_teams,
        )
        self.assertIsNotNone(reply)
        self.assertIn("Entrega registrada", reply or "")
        session_row = self._latest_session()
        self.assertEqual(session_row["step"], deliveries_flow.STATE_DONE)
        self.assertEqual(session_row["entregador_phone"], phone)
        self.assertEqual(session_row["obra_codigo"], "25180")
        self.assertEqual(session_row["recebedor_nome"], "Joao Silva")
        self.assertEqual(session_row["foto_media_id"], "media_12345")
        self.assertIsNone(session_row.get("observacao"))
        self.assertIsNotNone(session_row.get("finished_at"))

        sessions = self.fake_supabase.storage[DELIVERY_SESSIONS_TABLE]
        self.assertEqual(len(sessions), 1)

        deliveries = self.fake_supabase.storage[DELIVERIES_TABLE]
        self.assertEqual(len(deliveries), 1)
        delivery_row = deliveries[0]
        self.assertEqual(delivery_row["obra_codigo"], "25180")
        self.assertEqual(delivery_row["entregador_phone"], phone)
        self.assertEqual(delivery_row["recebedor_nome"], "Joao Silva")
        self.assertIsNone(delivery_row.get("observacao"))
        self.assertTrue(delivery_row["foto_path"].startswith("25180/"))
        self.assertEqual(delivery_row.get("foto_url"), "https://storage.test/signed/25180/file.jpg")

        self.assertEqual(len(self.teams_events), 2)
        self.assertEqual(self.teams_events[-1][0], "finish")
        finish_payload = self.teams_events[-1][1]
        self.assertEqual(finish_payload.get("obra_codigo"), "25180")
        self.assertEqual(finish_payload.get("recebedor_nome"), "Joao Silva")
        self.assertIsNone(finish_payload.get("observacao"))
        self.assertEqual(finish_payload.get("foto_url"), "https://storage.test/signed/25180/file.jpg")


if __name__ == "__main__":
    unittest.main()
