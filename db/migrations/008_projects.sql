-- Universal projects: dump & sort containers
-- Active context on users; link tasks/expenses/reminders; contacts via M2M

CREATE TABLE IF NOT EXISTS public.projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_user_lower_name
    ON public.projects (user_id, lower(name));

CREATE INDEX IF NOT EXISTS idx_projects_user_status
    ON public.projects (user_id, status);

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS active_project_id UUID REFERENCES public.projects(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS prefs JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS public.project_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'user_dump' CHECK (source IN ('user_dump', 'agent')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_project_notes_project_created
    ON public.project_notes (project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS public.project_contacts (
    project_id UUID NOT NULL REFERENCES public.projects(id) ON DELETE CASCADE,
    contact_id UUID NOT NULL REFERENCES public.contacts(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, contact_id)
);

ALTER TABLE public.tasks
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES public.projects(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON public.tasks (project_id);

ALTER TABLE public.expenses
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES public.projects(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_expenses_project_id ON public.expenses (project_id);

ALTER TABLE public.reminders
    ADD COLUMN IF NOT EXISTS project_id UUID REFERENCES public.projects(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_reminders_project_id ON public.reminders (project_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.projects TO service_role, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.project_notes TO service_role, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.project_contacts TO service_role, authenticated;
