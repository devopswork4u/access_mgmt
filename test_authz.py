import os
import tempfile
import unittest
from unittest.mock import patch

import store
from authz import permissions_for_groups


class AuthorizationTests(unittest.TestCase):
    def test_group_claims_map_to_capabilities(self):
        authorization = {
            "admin_groups": ["portal-admin"],
            "requester_groups": ["portal-requester"],
            "approver_groups": {
                "Tournament Operations": "tournament-approvers",
                "Membership & Participation": "membership-approvers",
            },
        }

        permissions = permissions_for_groups(
            ["portal-requester", "tournament-approvers"], authorization
        )

        self.assertTrue(permissions["can_request"])
        self.assertFalse(permissions["is_admin"])
        self.assertEqual(permissions["approver_departments"], {"Tournament Operations"})

    def test_approval_filter_uses_authorized_departments(self):
        with tempfile.TemporaryDirectory() as directory:
            database = os.path.join(directory, "portal.db")
            with patch.object(store, "DB_PATH", database):
                store.init()
                self._create_request("tournament-approvers", "Tournament Operations")
                self._create_request("ops.owner", "Tournament Operations")
                self._create_request("membership-approvers", "Membership & Participation")

                requests = store.list_requests(
                    status="Pending", approver_departments=["Tournament Operations"]
                )
                no_department_access = store.list_requests(approver_departments=[])

        self.assertEqual(
            {request["approver"] for request in requests},
            {"tournament-approvers", "ops.owner"},
        )
        self.assertEqual(no_department_access, [])

    @staticmethod
    def _create_request(approver, department):
        store.create_request({
            "requestor": "user-123",
            "target_user": "jane.doe",
            "department": department,
            "database_name": "usta_tournaments",
            "db_group": "usta_tournaments_ro",
            "tables": [],
            "access_level": "Read",
            "justification": "Unit test",
            "duration": "Permanent",
            "expiry": None,
            "approver": approver,
            "scope": "National",
        })


if __name__ == "__main__":
    unittest.main()