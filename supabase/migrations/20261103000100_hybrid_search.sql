-- InsightForge -- hybrid retrieval: pgvector cosine + Postgres full-text,
-- fused with Reciprocal Rank Fusion (RRF).
--
-- This targets public.chunks, the table backend/db.py reads. If your project
-- names it `document_chunks`, replace every `public.chunks` below.
--
-- Apply once in the Supabase SQL Editor (or `supabase db push`).

-- 1) Full-text column -------------------------------------------------------
-- to_tsvector('english', ...) with a literal regconfig is immutable, which a
-- generated column requires; the one-argument form is only stable.
alter table public.chunks
    add column if not exists fts tsvector
    generated always as (to_tsvector('english', coalesce(content, ''))) stored;

create index if not exists chunks_fts_gin_idx
    on public.chunks using gin (fts);

-- Optional: IVFFlat speeds up cosine scans on large tables but lowers recall
-- while the table is small. Uncomment once you have a few thousand chunks.
-- create index if not exists chunks_embedding_ivfflat_idx
--     on public.chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- 2) RRF function -----------------------------------------------------------
-- Each ranked list contributes 1 / (rrf_k + rank); a chunk that both the vector
-- scan and the text query like accumulates both terms and wins. Ranks, not raw
-- scores, are fused, so cosine (0..1) and ts_rank_cd (unbounded) never need to
-- be normalised against each other.
drop function if exists public.hybrid_search_chunks(text, vector, integer, uuid, uuid, integer);

create or replace function public.hybrid_search_chunks(
    query_text         text,
    query_embedding    vector(384),
    match_count        integer default 6,
    filter_user_id     uuid    default null,
    filter_document_id uuid    default null,
    rrf_k              integer default 60
)
returns table (
    chunk_id     uuid,
    document_id  uuid,
    content      text,
    page_number  integer,
    similarity   double precision,
    rrf_score    double precision,
    vector_rank  bigint,
    fts_rank     bigint
)
language sql
stable
security invoker
set search_path = public
as $$
    with scoped as (
        select c.id, c.document_id, c.content, c.page_number, c.embedding, c.fts
        from public.chunks c
        -- Strict equality: a null filter_user_id matches nothing rather than
        -- silently searching every user's chunks.
        where c.user_id = filter_user_id
          and (filter_document_id is null or c.document_id = filter_document_id)
    ),
    parsed as (
        -- websearch_to_tsquery never raises on user input, unlike to_tsquery,
        -- and yields an empty query for blank/punctuation-only text.
        select websearch_to_tsquery('english', coalesce(btrim(query_text), '')) as tsq
    ),
    vector_hits as (
        select s.id,
               row_number() over (order by s.embedding <=> query_embedding) as rank,
               1 - (s.embedding <=> query_embedding) as similarity
        from scoped s
        order by s.embedding <=> query_embedding
        limit greatest(coalesce(match_count, 6) * 5, 50)
    ),
    text_hits as (
        select s.id,
               row_number() over (order by ts_rank_cd(s.fts, p.tsq) desc) as rank
        from scoped s
        cross join parsed p
        where s.fts @@ p.tsq
        order by ts_rank_cd(s.fts, p.tsq) desc
        limit greatest(coalesce(match_count, 6) * 5, 50)
    ),
    fused as (
        select coalesce(v.id, t.id) as id,
               coalesce(1.0 / (coalesce(rrf_k, 60) + v.rank), 0)
             + coalesce(1.0 / (coalesce(rrf_k, 60) + t.rank), 0) as rrf_score,
               v.rank as vector_rank,
               t.rank as fts_rank,
               v.similarity as similarity
        from vector_hits v
        full outer join text_hits t on t.id = v.id
    )
    select c.id as chunk_id,
           c.document_id,
           c.content,
           c.page_number,
           coalesce(f.similarity, 0)::double precision as similarity,
           f.rrf_score::double precision,
           f.vector_rank,
           f.fts_rank
    from fused f
    join public.chunks c on c.id = f.id
    order by f.rrf_score desc, c.page_number asc, c.id
    limit greatest(coalesce(match_count, 6), 1);
$$;

comment on function public.hybrid_search_chunks(text, vector, integer, uuid, uuid, integer) is
    'Reciprocal Rank Fusion of pgvector cosine similarity and Postgres full-text ranking.';

-- The backend calls this with the service_role key; no anonymous access.
revoke all on function public.hybrid_search_chunks(text, vector, integer, uuid, uuid, integer) from public;
revoke all on function public.hybrid_search_chunks(text, vector, integer, uuid, uuid, integer) from anon;
grant execute on function public.hybrid_search_chunks(text, vector, integer, uuid, uuid, integer) to authenticated;
grant execute on function public.hybrid_search_chunks(text, vector, integer, uuid, uuid, integer) to service_role;

-- Smoke test (expect rows ordered by rrf_score):
-- select chunk_id, page_number, round(rrf_score::numeric, 5) as rrf, vector_rank, fts_rank
-- from public.hybrid_search_chunks(
--     'isolation forest contamination', (select embedding from public.chunks limit 1),
--     5, (select user_id from public.chunks limit 1), null, 60
-- );
