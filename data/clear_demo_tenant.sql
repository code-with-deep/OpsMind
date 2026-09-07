-- Clear demo tenant business + RAG + investigation memory (keep tenants row).
DO $$
DECLARE
  tid uuid;
BEGIN
  SELECT id INTO tid FROM tenants WHERE slug = 'demo' LIMIT 1;
  IF tid IS NULL THEN
    RAISE NOTICE 'No demo tenant';
    RETURN;
  END IF;

  DELETE FROM returns WHERE tenant_id = tid;
  DELETE FROM shipments WHERE tenant_id = tid;
  DELETE FROM inventory_snapshots WHERE tenant_id = tid;
  DELETE FROM order_items WHERE tenant_id = tid;
  DELETE FROM orders WHERE tenant_id = tid;
  DELETE FROM campaigns WHERE tenant_id = tid;
  DELETE FROM carriers WHERE tenant_id = tid;
  DELETE FROM products WHERE tenant_id = tid;
  DELETE FROM daily_metrics WHERE tenant_id = tid;

  DELETE FROM document_chunks WHERE tenant_id = tid;
  DELETE FROM documents WHERE tenant_id = tid;

  DELETE FROM case_summaries WHERE tenant_id = tid;
  DELETE FROM reviews WHERE tenant_id = tid;
  DELETE FROM findings WHERE tenant_id = tid;
  DELETE FROM tool_invocations WHERE tenant_id = tid;
  DELETE FROM investigation_events WHERE tenant_id = tid;
  DELETE FROM investigations WHERE tenant_id = tid;
  DELETE FROM ingest_jobs WHERE tenant_id = tid;

  RAISE NOTICE 'Cleared demo tenant %', tid;
END $$;

SELECT 'products' AS t, COUNT(*)::int AS n
FROM products p JOIN tenants t ON t.id = p.tenant_id WHERE t.slug = 'demo'
UNION ALL
SELECT 'orders', COUNT(*)::int
FROM orders o JOIN tenants t ON t.id = o.tenant_id WHERE t.slug = 'demo'
UNION ALL
SELECT 'daily_metrics', COUNT(*)::int
FROM daily_metrics m JOIN tenants t ON t.id = m.tenant_id WHERE t.slug = 'demo'
UNION ALL
SELECT 'documents', COUNT(*)::int
FROM documents d JOIN tenants t ON t.id = d.tenant_id WHERE t.slug = 'demo'
UNION ALL
SELECT 'investigations', COUNT(*)::int
FROM investigations i JOIN tenants t ON t.id = i.tenant_id WHERE t.slug = 'demo';
