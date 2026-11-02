import os
import tempfile
import unittest
from unittest.mock import patch

import store
from authz import database_username_from_claims, permissions_for_roles


class AuthorizationTests(unittest.TestCase):
    def test_database_username_comes_from_signed_identity(self):
        self.assertEqual(
            database_username_from_claims({"preferred_username": "Elena.Rios", "email": "other@example.com"}),
            "elena.rios",
        )
        self.assertEqual(
            database_username_from_claims({"email": "kaushikrahul08@example.com"}),
            "kaushikrahul08",
        )

    def test_database_username_requires_identity_claim(self):
        with self.assertRaises(ValueError):
            database_username_from_claims({"sub": "opaque-subject"})

    def test_entra_roles_map_to_capabilities(self):
        authorization = {
            "admin_roles": ["Portal.Admin"],
            "requester_roles": ["Portal.Requester"],
            "approver_roles": {
                "Tournament Operations": "Approver.TournamentOperations",
                "Membership & Participation": "Approver.Membership",
            },
        }

        permissions = permissions_for_roles(
            ["Portal.Requester", "Approver.TournamentOperations"], authorization
        )

        self.assertTrue(permissions["can_request"])
        self.assertFalse(permissions["is_admin"])
        self.assertEqual(permissions["approver_departments"], {"Tournament Operations"})

    def test_portal_admin_role_can_approve_all_departments(self):
        authorization = {
            "admin_roles": ["Portal.Admin"],
            "approver_roles": {
                "Tournament Operations": "Approver.TournamentOperations",
                "Membership & Participation": "Approver.Membership",
                "Player Development": "Approver.PlayerDevelopment",
            },
        }

        permissions = permissions_for_roles(["Portal.Admin"], authorization)

        self.assertTrue(permissions["is_admin"])
        self.assertEqual(
            permissions["approver_departments"],
            {"Tournament Operations", "Membership & Participation", "Player Development"},
        )

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