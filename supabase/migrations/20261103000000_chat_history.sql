-- InsightForge -- persistent research-paper chat.
-- Apply in Supabase -> SQL Editor (or `supabase db push`).
--
-- One row per message (role 'user' or 'assistant'), so a reload can rebuild the
-- Q&A pairs in order and keep their page citations. Scope is enforced twice:
-- the foreign keys tie every row to its owner and its document, and RLS
-- re-checks auth.uid() on every read/write that comes from a user session.

create extension if not exists pgcrypto;

create table if not exists public.chat_history (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references auth.users (id) on delete cascade,
    document_id uuid not null references public.documents (id) on delete cascade,
    role        text not null check (role in ('user', 'assistant')),
    content     text not null check (length(btrim(content)) > 0),
    citations   jsonb,
    created_at  timestamptz not null default now()
);

comment on table public.chat_history is
    'Per-document Q&A turns for InsightForge; one row per user or assistant message.';

-- The API always reads one document at a time, oldest message first.
create index if not exists chat_history_document_created_at_idx
    on public.chat_history (document_id, created_at);

-- Also covers the Clear Chat delete, which filters on both columns.
create index if not exists chat_history_user_document_idx
    on public.chat_history (user_id, document_id, created_at);

alter table public.chat_history enable row level security;

drop policy if exists chat_history_select_own on public.chat_history;
create policy chat_history_select_own
    on public.chat_history
    for select
    to authenticated
    using (auth.uid() = user_id);

drop policy if exists chat_history_insert_own on public.chat_history;
create policy chat_history_insert_own
    on public.chat_history
    for insert
    to authenticated
    with check (auth.uid() = user_id);

-- The backend uses the service_role key and bypasses RLS, but Clear Chat is a
-- user action: without this policy a direct client delete would silently do
-- nothing. Note there is deliberately no UPDATE policy -- turns are immutable.
drop policy if exists chat_history_delete_own on public.chat_history;
create policy chat_history_delete_own
    on public.chat_history
    for delete
    to authenticated
    using (auth.uid() = user_id);

revoke all on public.chat_history from anon;
grant select, insert, delete on public.chat_history to authenticated;
