-- Multi-user invite + multi-channel (Telegram / VK)
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS paid_until DATE;
ALTER TABLE public.users ALTER COLUMN telegram_id DROP NOT NULL;

CREATE TABLE IF NOT EXISTS public.user_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    channel TEXT NOT NULL CHECK (channel IN ('telegram', 'vk')),
    external_id TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (channel, external_id)
);

CREATE INDEX IF NOT EXISTS idx_user_identities_user_id
    ON public.user_identities(user_id);

INSERT INTO public.user_identities (user_id, channel, external_id)
SELECT id, 'telegram', telegram_id::text
FROM public.users
WHERE telegram_id IS NOT NULL
ON CONFLICT (channel, external_id) DO NOTHING;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.user_identities TO service_role, authenticated;
