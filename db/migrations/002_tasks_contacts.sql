-- Tasks (TODO list)
CREATE TABLE IF NOT EXISTS public.tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    due_date DATE,
    due_time TIME,
    priority TEXT DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'done', 'cancelled')),
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- Contacts (address book for broadcasts)
CREATE TABLE IF NOT EXISTS public.contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    telegram_username TEXT,
    telegram_id BIGINT,
    company TEXT,
    role TEXT,
    notes TEXT,
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Contact groups for broadcasts
CREATE TABLE IF NOT EXISTS public.contact_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Many-to-many: contacts <-> groups
CREATE TABLE IF NOT EXISTS public.contact_group_members (
    contact_id UUID REFERENCES public.contacts(id) ON DELETE CASCADE,
    group_id UUID REFERENCES public.contact_groups(id) ON DELETE CASCADE,
    PRIMARY KEY (contact_id, group_id)
);

-- Broadcast history
CREATE TABLE IF NOT EXISTS public.broadcasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES public.users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    recipient_count INT DEFAULT 0,
    sent_count INT DEFAULT 0,
    failed_count INT DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'sending', 'completed', 'failed')),
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON public.tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_user_due ON public.tasks(user_id, due_date);
CREATE INDEX IF NOT EXISTS idx_contacts_user ON public.contacts(user_id);
CREATE INDEX IF NOT EXISTS idx_contacts_tags ON public.contacts USING GIN(tags);

-- Grants
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.tasks TO service_role, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.contacts TO service_role, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.contact_groups TO service_role, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.contact_group_members TO service_role, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.broadcasts TO service_role, authenticated;
