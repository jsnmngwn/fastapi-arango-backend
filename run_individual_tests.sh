#!/bin/bash
# Simple script to run our tests one at a time

cd /home/jason/github/vb-stat-logger

# Run each test individually
for test in TestOrganizationAPI::test_create_organization \
           TestOrganizationAPI::test_get_organizations \
           TestOrganizationAPI::test_get_organizations_with_pagination \
           TestOrganizationAPI::test_get_organizations_active_only \
           TestOrganizationAPI::test_get_organization_by_id \
           TestOrganizationAPI::test_get_nonexistent_organization \
           TestOrganizationAPI::test_update_organization \
           TestOrganizationAPI::test_update_nonexistent_organization \
           TestOrganizationAPI::test_delete_organization \
           TestOrganizationAPI::test_delete_nonexistent_organization \
           TestOrganizationDeletionConstraint::test_delete_organization_with_team_links_mock \
           TestOrganizationDeletionConstraint::test_delete_organization_with_actual_edge
do
    echo "Running test: $test"
    poetry run pytest backend/tests/test_organizations.py::$test -v
    if [ $? -ne 0 ]; then
        echo "Test $test failed!"
        exit 1
    fi
    echo "Test $test passed."
    echo
done

echo "All tests passed successfully!"
