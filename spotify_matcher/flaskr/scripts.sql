DELETE FROM invitations
WHERE id not in (SELECT invitation_id FROM accepted_invitations)
