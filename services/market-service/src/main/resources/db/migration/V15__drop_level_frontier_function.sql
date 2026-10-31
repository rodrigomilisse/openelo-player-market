-- The frontier lookup moved back into the open-orders query, where its level parameter is
-- typed by the entity mapping.
DROP FUNCTION level_frontier(UUID, side, BIGINT);
