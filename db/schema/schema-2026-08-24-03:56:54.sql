--
-- PostgreSQL database dump
--

\restrict Gebf7FpDRTD3PY8ANfOChDaTQrIFwjert3JDJu3CbBjJKynL81puAbRu4UhuSto

-- Dumped from database version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: StorageType; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public."StorageType" AS ENUM (
    'duckdb',
    'postgresql',
    'mysql',
    'access',
    'mssql'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: AIProvider; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."AIProvider" (
    id integer NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    "isLocal" boolean DEFAULT false NOT NULL,
    "requiresApiKey" boolean DEFAULT true NOT NULL,
    "defaultEndpoint" text,
    enabled boolean DEFAULT true NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL
);


--
-- Name: AIProvider_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."AIProvider_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: AIProvider_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."AIProvider_id_seq" OWNED BY public."AIProvider".id;


--
-- Name: AIRecipeSession; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."AIRecipeSession" (
    id text NOT NULL,
    "userId" text NOT NULL,
    "datasetId" text,
    status text DEFAULT 'active'::text NOT NULL,
    stage text DEFAULT 'greeting'::text NOT NULL,
    messages jsonb DEFAULT '[]'::jsonb NOT NULL,
    state jsonb DEFAULT '{}'::jsonb NOT NULL,
    "schemaSnapshot" jsonb,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL
);


--
-- Name: Account; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Account" (
    id text NOT NULL,
    "userId" text NOT NULL,
    type text NOT NULL,
    provider text NOT NULL,
    "providerAccountId" text NOT NULL,
    refresh_token text,
    access_token text,
    expires_at integer,
    token_type text,
    scope text,
    id_token text,
    session_state text
);


--
-- Name: Chat; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Chat" (
    id integer NOT NULL,
    "userId" text NOT NULL,
    title character varying(255),
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL
);


--
-- Name: Chat_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Chat_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Chat_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Chat_id_seq" OWNED BY public."Chat".id;


--
-- Name: DataPreparationRule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."DataPreparationRule" (
    id text NOT NULL,
    "datasetId" text NOT NULL,
    "userId" text NOT NULL,
    name text NOT NULL,
    description text,
    operations jsonb NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    "ruleGroup" text DEFAULT '00'::text NOT NULL,
    "isShared" boolean DEFAULT false NOT NULL
);


--
-- Name: DatasetDescription; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."DatasetDescription" (
    id text NOT NULL,
    "datasetId" text NOT NULL,
    description text NOT NULL,
    "generatedAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "usedModel" text,
    "userId" text NOT NULL
);


--
-- Name: GlobalSettings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."GlobalSettings" (
    id integer DEFAULT 1 NOT NULL,
    "demoMode" boolean DEFAULT false NOT NULL,
    "maxRegistrations" integer,
    "emailVerificationTimeout" integer DEFAULT 24,
    "emailSender" text DEFAULT 'no-reply@replace-with-your-domain'::text,
    "publicUrl" text DEFAULT 'https://replace-with-your-external-host-name'::text,
    "registrationGracePeriodHours" integer DEFAULT 24 NOT NULL,
    welcome text DEFAULT 'Welcome to Statisticians Workbench!'::text,
    "passwordPolicy" text DEFAULT 'medium'::text NOT NULL,
    "passwordPolicyCustom" jsonb,
    "defaultMaxUploadSizeMB" integer DEFAULT 0 NOT NULL,
    "defaultMaxUploadCount" integer DEFAULT 0 NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    "platformMaxUploadSizeMB" integer DEFAULT 10 NOT NULL
);


--
-- Name: Message; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Message" (
    id integer NOT NULL,
    "chatId" integer NOT NULL,
    role character varying(20) NOT NULL,
    content text NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: Message_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Message_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Message_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Message_id_seq" OWNED BY public."Message".id;


--
-- Name: NotebookImport; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."NotebookImport" (
    id text NOT NULL,
    "userId" text NOT NULL,
    "notebookName" text NOT NULL,
    "notebookContent" jsonb DEFAULT '{}'::jsonb NOT NULL,
    "importedAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    "tablesCreated" text[],
    "storageType" text DEFAULT 'duckdb'::text NOT NULL,
    metadata jsonb,
    "markdownContent" text,
    "errorLog" text,
    "notebookGroup" text DEFAULT '00'::text NOT NULL,
    "connectionId" integer,
    "createDatabase" boolean DEFAULT false NOT NULL,
    "isShared" boolean DEFAULT false NOT NULL
);


--
-- Name: PasswordResetToken; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."PasswordResetToken" (
    id text NOT NULL,
    token text NOT NULL,
    "userId" text NOT NULL,
    "expiresAt" timestamp(3) without time zone NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: ProviderModel; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."ProviderModel" (
    id integer NOT NULL,
    "providerCode" text NOT NULL,
    "modelName" text NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    preferred boolean DEFAULT false NOT NULL,
    comment text,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL
);


--
-- Name: ProviderModel_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."ProviderModel_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ProviderModel_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."ProviderModel_id_seq" OWNED BY public."ProviderModel".id;


--
-- Name: Recipe; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Recipe" (
    id text NOT NULL,
    "userId" text NOT NULL,
    name text NOT NULL,
    description text,
    "datasetId" text,
    stages jsonb NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    "recipeGroup" text DEFAULT '00'::text NOT NULL,
    "isShared" boolean DEFAULT false NOT NULL,
    "forkedFrom" text,
    "forkedFromName" text,
    status text DEFAULT 'draft'::text NOT NULL
);


--
-- Name: RecipeExecution; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."RecipeExecution" (
    id text NOT NULL,
    "recipeId" text NOT NULL,
    "userId" text NOT NULL,
    status text NOT NULL,
    progress integer DEFAULT 0 NOT NULL,
    result jsonb,
    error text,
    "startedAt" timestamp(3) without time zone,
    "completedAt" timestamp(3) without time zone,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL
);


--
-- Name: RecipePreparationRule; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."RecipePreparationRule" (
    id text NOT NULL,
    "recipeId" text NOT NULL,
    "ruleId" text NOT NULL,
    "order" integer NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL
);


--
-- Name: Session; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Session" (
    id text NOT NULL,
    "sessionToken" text NOT NULL,
    "userId" text NOT NULL,
    expires timestamp(3) without time zone NOT NULL
);


--
-- Name: Translation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."Translation" (
    id integer NOT NULL,
    key text NOT NULL,
    language text NOT NULL,
    value text NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL
);


--
-- Name: Translation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."Translation_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: Translation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."Translation_id_seq" OWNED BY public."Translation".id;


--
-- Name: User; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."User" (
    id text NOT NULL,
    email text NOT NULL,
    password text NOT NULL,
    name text,
    "isAdmin" boolean DEFAULT false NOT NULL,
    "emailVerified" timestamp(3) without time zone,
    "bccRegistrations" boolean DEFAULT false NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    "deletedAt" timestamp(3) without time zone,
    "maxUploadSizeMB" integer DEFAULT 0 NOT NULL,
    "maxUploadCount" integer DEFAULT 0 NOT NULL,
    "userGroup" text DEFAULT '00'::text NOT NULL,
    "emailNotifications" boolean DEFAULT false NOT NULL,
    "darkMode" boolean DEFAULT false NOT NULL,
    language text DEFAULT 'en'::text NOT NULL,
    "defaultAIConnectionId" integer,
    "isExampleUser" boolean DEFAULT false NOT NULL,
    "isGroupAdmin" boolean DEFAULT false NOT NULL
);


--
-- Name: UserAIConnection; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."UserAIConnection" (
    "connectionId" integer NOT NULL,
    "userId" text NOT NULL,
    name text NOT NULL,
    provider text NOT NULL,
    "apiKey" text,
    endpoint text,
    "defaultModel" text,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    "aiConnectionGroup" text DEFAULT '00'::text NOT NULL,
    "isShared" boolean DEFAULT false NOT NULL
);


--
-- Name: UserAIConnection_connectionId_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."UserAIConnection_connectionId_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: UserAIConnection_connectionId_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."UserAIConnection_connectionId_seq" OWNED BY public."UserAIConnection"."connectionId";


--
-- Name: UserDatabaseConnection; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."UserDatabaseConnection" (
    "connectionId" integer NOT NULL,
    "userId" text NOT NULL,
    name text NOT NULL,
    type text NOT NULL,
    host text NOT NULL,
    port integer NOT NULL,
    database text NOT NULL,
    username text NOT NULL,
    password text NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    "dbConnectionGroup" text DEFAULT '00'::text NOT NULL,
    "canCreateDatabase" boolean DEFAULT false NOT NULL,
    "canCreateTables" boolean DEFAULT false NOT NULL,
    "isShared" boolean DEFAULT false NOT NULL
);


--
-- Name: UserDatabaseConnection_connectionId_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."UserDatabaseConnection_connectionId_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: UserDatabaseConnection_connectionId_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."UserDatabaseConnection_connectionId_seq" OWNED BY public."UserDatabaseConnection"."connectionId";


--
-- Name: UserDataset; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."UserDataset" (
    id text NOT NULL,
    "userId" text NOT NULL,
    name text NOT NULL,
    description text,
    "sourceType" text DEFAULT 'upload'::text NOT NULL,
    "storageType" public."StorageType",
    "sourceConnectionId" integer,
    "databaseName" text,
    "tableName" text,
    "originalFileName" text,
    "fileSize" bigint,
    "filePath" text,
    "dataSnapshot" jsonb,
    "isView" boolean DEFAULT false,
    "datasetGroup" text DEFAULT '00'::text NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    materialized boolean DEFAULT false NOT NULL,
    "outputSchema" jsonb,
    "sourceConnectionIds" jsonb,
    "sourceDatasetIds" jsonb,
    status text DEFAULT 'draft'::text NOT NULL,
    "virtualSql" jsonb,
    "isShared" boolean DEFAULT false NOT NULL
);


--
-- Name: UserGroup; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."UserGroup" (
    id text NOT NULL,
    "groupId" character varying(2) NOT NULL,
    "groupDescription" text DEFAULT 'Default'::text NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL
);


--
-- Name: VerificationToken; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."VerificationToken" (
    id text NOT NULL,
    token text NOT NULL,
    "userId" text NOT NULL,
    "expiresAt" timestamp(3) without time zone NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: VirtualDatasetChat; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."VirtualDatasetChat" (
    id text NOT NULL,
    "userId" text NOT NULL,
    "datasetId" text,
    "currentStage" text DEFAULT 'entry'::text NOT NULL,
    "contextData" jsonb DEFAULT '{}'::jsonb NOT NULL,
    messages jsonb DEFAULT '[]'::jsonb NOT NULL,
    status text DEFAULT 'active'::text NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL
);


--
-- Name: VisualizationInstance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."VisualizationInstance" (
    id integer NOT NULL,
    "userId" text NOT NULL,
    "visualizationTypeId" integer NOT NULL,
    "outputId" text,
    parameters jsonb NOT NULL,
    "dataSnapshot" jsonb,
    "generatedImageUrl" text,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL
);


--
-- Name: VisualizationInstance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."VisualizationInstance_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: VisualizationInstance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."VisualizationInstance_id_seq" OWNED BY public."VisualizationInstance".id;


--
-- Name: VisualizationType; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."VisualizationType" (
    id integer NOT NULL,
    name text NOT NULL,
    slug text NOT NULL,
    description text,
    "inputSchema" jsonb NOT NULL,
    "parameterSchema" jsonb NOT NULL,
    "defaultParameters" jsonb NOT NULL,
    renderer text DEFAULT 'client'::text NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    "createdAt" timestamp(3) without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL
);


--
-- Name: VisualizationType_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public."VisualizationType_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: VisualizationType_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public."VisualizationType_id_seq" OWNED BY public."VisualizationType".id;


--
-- Name: user_audio_presets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_audio_presets (
    id integer NOT NULL,
    "userId" text NOT NULL,
    "chatType" text NOT NULL,
    "voiceName" text,
    speed double precision DEFAULT 1.0 NOT NULL,
    pitch double precision DEFAULT 1.0 NOT NULL,
    "updatedAt" timestamp(3) without time zone NOT NULL,
    volume double precision DEFAULT 1.0,
    "micVolume" double precision DEFAULT 1.0,
    "micMuted" boolean DEFAULT false,
    "speakerMuted" boolean DEFAULT false
);


--
-- Name: user_audio_presets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_audio_presets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_audio_presets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_audio_presets_id_seq OWNED BY public.user_audio_presets.id;


--
-- Name: AIProvider id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."AIProvider" ALTER COLUMN id SET DEFAULT nextval('public."AIProvider_id_seq"'::regclass);


--
-- Name: Chat id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Chat" ALTER COLUMN id SET DEFAULT nextval('public."Chat_id_seq"'::regclass);


--
-- Name: Message id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Message" ALTER COLUMN id SET DEFAULT nextval('public."Message_id_seq"'::regclass);


--
-- Name: ProviderModel id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."ProviderModel" ALTER COLUMN id SET DEFAULT nextval('public."ProviderModel_id_seq"'::regclass);


--
-- Name: Translation id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Translation" ALTER COLUMN id SET DEFAULT nextval('public."Translation_id_seq"'::regclass);


--
-- Name: UserAIConnection connectionId; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."UserAIConnection" ALTER COLUMN "connectionId" SET DEFAULT nextval('public."UserAIConnection_connectionId_seq"'::regclass);


--
-- Name: UserDatabaseConnection connectionId; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."UserDatabaseConnection" ALTER COLUMN "connectionId" SET DEFAULT nextval('public."UserDatabaseConnection_connectionId_seq"'::regclass);


--
-- Name: VisualizationInstance id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VisualizationInstance" ALTER COLUMN id SET DEFAULT nextval('public."VisualizationInstance_id_seq"'::regclass);


--
-- Name: VisualizationType id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VisualizationType" ALTER COLUMN id SET DEFAULT nextval('public."VisualizationType_id_seq"'::regclass);


--
-- Name: user_audio_presets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_audio_presets ALTER COLUMN id SET DEFAULT nextval('public.user_audio_presets_id_seq'::regclass);


--
-- Name: AIProvider AIProvider_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."AIProvider"
    ADD CONSTRAINT "AIProvider_pkey" PRIMARY KEY (id);


--
-- Name: AIRecipeSession AIRecipeSession_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."AIRecipeSession"
    ADD CONSTRAINT "AIRecipeSession_pkey" PRIMARY KEY (id);


--
-- Name: Account Account_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Account"
    ADD CONSTRAINT "Account_pkey" PRIMARY KEY (id);


--
-- Name: Chat Chat_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Chat"
    ADD CONSTRAINT "Chat_pkey" PRIMARY KEY (id);


--
-- Name: DataPreparationRule DataPreparationRule_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."DataPreparationRule"
    ADD CONSTRAINT "DataPreparationRule_pkey" PRIMARY KEY (id);


--
-- Name: DatasetDescription DatasetDescription_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."DatasetDescription"
    ADD CONSTRAINT "DatasetDescription_pkey" PRIMARY KEY (id);


--
-- Name: GlobalSettings GlobalSettings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."GlobalSettings"
    ADD CONSTRAINT "GlobalSettings_pkey" PRIMARY KEY (id);


--
-- Name: Message Message_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Message"
    ADD CONSTRAINT "Message_pkey" PRIMARY KEY (id);


--
-- Name: NotebookImport NotebookImport_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."NotebookImport"
    ADD CONSTRAINT "NotebookImport_pkey" PRIMARY KEY (id);


--
-- Name: PasswordResetToken PasswordResetToken_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."PasswordResetToken"
    ADD CONSTRAINT "PasswordResetToken_pkey" PRIMARY KEY (id);


--
-- Name: ProviderModel ProviderModel_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."ProviderModel"
    ADD CONSTRAINT "ProviderModel_pkey" PRIMARY KEY (id);


--
-- Name: RecipeExecution RecipeExecution_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."RecipeExecution"
    ADD CONSTRAINT "RecipeExecution_pkey" PRIMARY KEY (id);


--
-- Name: RecipePreparationRule RecipePreparationRule_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."RecipePreparationRule"
    ADD CONSTRAINT "RecipePreparationRule_pkey" PRIMARY KEY (id);


--
-- Name: Recipe Recipe_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Recipe"
    ADD CONSTRAINT "Recipe_pkey" PRIMARY KEY (id);


--
-- Name: Session Session_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Session"
    ADD CONSTRAINT "Session_pkey" PRIMARY KEY (id);


--
-- Name: Translation Translation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Translation"
    ADD CONSTRAINT "Translation_pkey" PRIMARY KEY (id);


--
-- Name: UserAIConnection UserAIConnection_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."UserAIConnection"
    ADD CONSTRAINT "UserAIConnection_pkey" PRIMARY KEY ("connectionId");


--
-- Name: UserDatabaseConnection UserDatabaseConnection_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."UserDatabaseConnection"
    ADD CONSTRAINT "UserDatabaseConnection_pkey" PRIMARY KEY ("connectionId");


--
-- Name: UserDataset UserDataset_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."UserDataset"
    ADD CONSTRAINT "UserDataset_pkey" PRIMARY KEY (id);


--
-- Name: UserGroup UserGroup_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."UserGroup"
    ADD CONSTRAINT "UserGroup_pkey" PRIMARY KEY (id);


--
-- Name: User User_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."User"
    ADD CONSTRAINT "User_pkey" PRIMARY KEY (id);


--
-- Name: VerificationToken VerificationToken_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VerificationToken"
    ADD CONSTRAINT "VerificationToken_pkey" PRIMARY KEY (id);


--
-- Name: VirtualDatasetChat VirtualDatasetChat_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VirtualDatasetChat"
    ADD CONSTRAINT "VirtualDatasetChat_pkey" PRIMARY KEY (id);


--
-- Name: VisualizationInstance VisualizationInstance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VisualizationInstance"
    ADD CONSTRAINT "VisualizationInstance_pkey" PRIMARY KEY (id);


--
-- Name: VisualizationType VisualizationType_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VisualizationType"
    ADD CONSTRAINT "VisualizationType_pkey" PRIMARY KEY (id);


--
-- Name: user_audio_presets user_audio_presets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_audio_presets
    ADD CONSTRAINT user_audio_presets_pkey PRIMARY KEY (id);


--
-- Name: AIProvider_code_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "AIProvider_code_key" ON public."AIProvider" USING btree (code);


--
-- Name: AIRecipeSession_datasetId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "AIRecipeSession_datasetId_idx" ON public."AIRecipeSession" USING btree ("datasetId");


--
-- Name: AIRecipeSession_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "AIRecipeSession_status_idx" ON public."AIRecipeSession" USING btree (status);


--
-- Name: AIRecipeSession_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "AIRecipeSession_userId_idx" ON public."AIRecipeSession" USING btree ("userId");


--
-- Name: Account_provider_providerAccountId_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "Account_provider_providerAccountId_key" ON public."Account" USING btree (provider, "providerAccountId");


--
-- Name: Account_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Account_userId_idx" ON public."Account" USING btree ("userId");


--
-- Name: Chat_updatedAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Chat_updatedAt_idx" ON public."Chat" USING btree ("updatedAt");


--
-- Name: Chat_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Chat_userId_idx" ON public."Chat" USING btree ("userId");


--
-- Name: DataPreparationRule_datasetId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "DataPreparationRule_datasetId_idx" ON public."DataPreparationRule" USING btree ("datasetId");


--
-- Name: DataPreparationRule_datasetId_name_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "DataPreparationRule_datasetId_name_key" ON public."DataPreparationRule" USING btree ("datasetId", name);


--
-- Name: DataPreparationRule_ruleGroup_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "DataPreparationRule_ruleGroup_idx" ON public."DataPreparationRule" USING btree ("ruleGroup");


--
-- Name: DataPreparationRule_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "DataPreparationRule_userId_idx" ON public."DataPreparationRule" USING btree ("userId");


--
-- Name: DatasetDescription_datasetId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "DatasetDescription_datasetId_idx" ON public."DatasetDescription" USING btree ("datasetId");


--
-- Name: DatasetDescription_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "DatasetDescription_userId_idx" ON public."DatasetDescription" USING btree ("userId");


--
-- Name: Message_chatId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Message_chatId_idx" ON public."Message" USING btree ("chatId");


--
-- Name: Message_createdAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Message_createdAt_idx" ON public."Message" USING btree ("createdAt");


--
-- Name: NotebookImport_importedAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "NotebookImport_importedAt_idx" ON public."NotebookImport" USING btree ("importedAt");


--
-- Name: NotebookImport_notebookGroup_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "NotebookImport_notebookGroup_idx" ON public."NotebookImport" USING btree ("notebookGroup");


--
-- Name: NotebookImport_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "NotebookImport_status_idx" ON public."NotebookImport" USING btree (status);


--
-- Name: NotebookImport_storageType_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "NotebookImport_storageType_idx" ON public."NotebookImport" USING btree ("storageType");


--
-- Name: NotebookImport_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "NotebookImport_userId_idx" ON public."NotebookImport" USING btree ("userId");


--
-- Name: PasswordResetToken_expiresAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "PasswordResetToken_expiresAt_idx" ON public."PasswordResetToken" USING btree ("expiresAt");


--
-- Name: PasswordResetToken_token_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "PasswordResetToken_token_key" ON public."PasswordResetToken" USING btree (token);


--
-- Name: PasswordResetToken_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "PasswordResetToken_userId_idx" ON public."PasswordResetToken" USING btree ("userId");


--
-- Name: ProviderModel_providerCode_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "ProviderModel_providerCode_idx" ON public."ProviderModel" USING btree ("providerCode");


--
-- Name: ProviderModel_providerCode_modelName_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "ProviderModel_providerCode_modelName_key" ON public."ProviderModel" USING btree ("providerCode", "modelName");


--
-- Name: RecipeExecution_createdAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "RecipeExecution_createdAt_idx" ON public."RecipeExecution" USING btree ("createdAt");


--
-- Name: RecipeExecution_recipeId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "RecipeExecution_recipeId_idx" ON public."RecipeExecution" USING btree ("recipeId");


--
-- Name: RecipeExecution_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "RecipeExecution_status_idx" ON public."RecipeExecution" USING btree (status);


--
-- Name: RecipeExecution_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "RecipeExecution_userId_idx" ON public."RecipeExecution" USING btree ("userId");


--
-- Name: RecipePreparationRule_recipeId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "RecipePreparationRule_recipeId_idx" ON public."RecipePreparationRule" USING btree ("recipeId");


--
-- Name: RecipePreparationRule_recipeId_order_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "RecipePreparationRule_recipeId_order_key" ON public."RecipePreparationRule" USING btree ("recipeId", "order");


--
-- Name: RecipePreparationRule_ruleId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "RecipePreparationRule_ruleId_idx" ON public."RecipePreparationRule" USING btree ("ruleId");


--
-- Name: Recipe_createdAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Recipe_createdAt_idx" ON public."Recipe" USING btree ("createdAt");


--
-- Name: Recipe_datasetId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Recipe_datasetId_idx" ON public."Recipe" USING btree ("datasetId");


--
-- Name: Recipe_recipeGroup_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Recipe_recipeGroup_idx" ON public."Recipe" USING btree ("recipeGroup");


--
-- Name: Recipe_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Recipe_status_idx" ON public."Recipe" USING btree (status);


--
-- Name: Recipe_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Recipe_userId_idx" ON public."Recipe" USING btree ("userId");


--
-- Name: Session_expires_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Session_expires_idx" ON public."Session" USING btree (expires);


--
-- Name: Session_sessionToken_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "Session_sessionToken_key" ON public."Session" USING btree ("sessionToken");


--
-- Name: Session_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Session_userId_idx" ON public."Session" USING btree ("userId");


--
-- Name: Translation_key_language_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "Translation_key_language_key" ON public."Translation" USING btree (key, language);


--
-- Name: Translation_language_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "Translation_language_idx" ON public."Translation" USING btree (language);


--
-- Name: UserAIConnection_aiConnectionGroup_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "UserAIConnection_aiConnectionGroup_idx" ON public."UserAIConnection" USING btree ("aiConnectionGroup");


--
-- Name: UserAIConnection_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "UserAIConnection_userId_idx" ON public."UserAIConnection" USING btree ("userId");


--
-- Name: UserAIConnection_userId_name_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "UserAIConnection_userId_name_key" ON public."UserAIConnection" USING btree ("userId", name);


--
-- Name: UserDatabaseConnection_dbConnectionGroup_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "UserDatabaseConnection_dbConnectionGroup_idx" ON public."UserDatabaseConnection" USING btree ("dbConnectionGroup");


--
-- Name: UserDatabaseConnection_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "UserDatabaseConnection_userId_idx" ON public."UserDatabaseConnection" USING btree ("userId");


--
-- Name: UserDatabaseConnection_userId_name_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "UserDatabaseConnection_userId_name_key" ON public."UserDatabaseConnection" USING btree ("userId", name);


--
-- Name: UserDataset_createdAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "UserDataset_createdAt_idx" ON public."UserDataset" USING btree ("createdAt");


--
-- Name: UserDataset_datasetGroup_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "UserDataset_datasetGroup_idx" ON public."UserDataset" USING btree ("datasetGroup");


--
-- Name: UserDataset_sourceConnectionId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "UserDataset_sourceConnectionId_idx" ON public."UserDataset" USING btree ("sourceConnectionId");


--
-- Name: UserDataset_sourceType_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "UserDataset_sourceType_idx" ON public."UserDataset" USING btree ("sourceType");


--
-- Name: UserDataset_storageType_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "UserDataset_storageType_idx" ON public."UserDataset" USING btree ("storageType");


--
-- Name: UserDataset_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "UserDataset_userId_idx" ON public."UserDataset" USING btree ("userId");


--
-- Name: UserGroup_groupId_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "UserGroup_groupId_key" ON public."UserGroup" USING btree ("groupId");


--
-- Name: User_deletedAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "User_deletedAt_idx" ON public."User" USING btree ("deletedAt");


--
-- Name: User_email_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "User_email_key" ON public."User" USING btree (email);


--
-- Name: User_userGroup_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "User_userGroup_idx" ON public."User" USING btree ("userGroup");


--
-- Name: VerificationToken_expiresAt_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "VerificationToken_expiresAt_idx" ON public."VerificationToken" USING btree ("expiresAt");


--
-- Name: VerificationToken_token_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "VerificationToken_token_key" ON public."VerificationToken" USING btree (token);


--
-- Name: VerificationToken_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "VerificationToken_userId_idx" ON public."VerificationToken" USING btree ("userId");


--
-- Name: VirtualDatasetChat_datasetId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "VirtualDatasetChat_datasetId_idx" ON public."VirtualDatasetChat" USING btree ("datasetId");


--
-- Name: VirtualDatasetChat_status_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "VirtualDatasetChat_status_idx" ON public."VirtualDatasetChat" USING btree (status);


--
-- Name: VirtualDatasetChat_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "VirtualDatasetChat_userId_idx" ON public."VirtualDatasetChat" USING btree ("userId");


--
-- Name: VisualizationInstance_userId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "VisualizationInstance_userId_idx" ON public."VisualizationInstance" USING btree ("userId");


--
-- Name: VisualizationInstance_visualizationTypeId_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "VisualizationInstance_visualizationTypeId_idx" ON public."VisualizationInstance" USING btree ("visualizationTypeId");


--
-- Name: VisualizationType_enabled_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX "VisualizationType_enabled_idx" ON public."VisualizationType" USING btree (enabled);


--
-- Name: VisualizationType_slug_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "VisualizationType_slug_key" ON public."VisualizationType" USING btree (slug);


--
-- Name: user_audio_presets_userId_chatType_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "user_audio_presets_userId_chatType_key" ON public.user_audio_presets USING btree ("userId", "chatType");


--
-- Name: AIRecipeSession AIRecipeSession_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."AIRecipeSession"
    ADD CONSTRAINT "AIRecipeSession_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: Account Account_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Account"
    ADD CONSTRAINT "Account_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: Chat Chat_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Chat"
    ADD CONSTRAINT "Chat_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: DataPreparationRule DataPreparationRule_datasetId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."DataPreparationRule"
    ADD CONSTRAINT "DataPreparationRule_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES public."UserDataset"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: DataPreparationRule DataPreparationRule_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."DataPreparationRule"
    ADD CONSTRAINT "DataPreparationRule_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: DatasetDescription DatasetDescription_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."DatasetDescription"
    ADD CONSTRAINT "DatasetDescription_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: NotebookImport NotebookImport_connectionId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."NotebookImport"
    ADD CONSTRAINT "NotebookImport_connectionId_fkey" FOREIGN KEY ("connectionId") REFERENCES public."UserDatabaseConnection"("connectionId") ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: NotebookImport NotebookImport_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."NotebookImport"
    ADD CONSTRAINT "NotebookImport_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: PasswordResetToken PasswordResetToken_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."PasswordResetToken"
    ADD CONSTRAINT "PasswordResetToken_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: RecipeExecution RecipeExecution_recipeId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."RecipeExecution"
    ADD CONSTRAINT "RecipeExecution_recipeId_fkey" FOREIGN KEY ("recipeId") REFERENCES public."Recipe"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: RecipeExecution RecipeExecution_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."RecipeExecution"
    ADD CONSTRAINT "RecipeExecution_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: RecipePreparationRule RecipePreparationRule_recipeId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."RecipePreparationRule"
    ADD CONSTRAINT "RecipePreparationRule_recipeId_fkey" FOREIGN KEY ("recipeId") REFERENCES public."Recipe"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: RecipePreparationRule RecipePreparationRule_ruleId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."RecipePreparationRule"
    ADD CONSTRAINT "RecipePreparationRule_ruleId_fkey" FOREIGN KEY ("ruleId") REFERENCES public."DataPreparationRule"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: Recipe Recipe_datasetId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Recipe"
    ADD CONSTRAINT "Recipe_datasetId_fkey" FOREIGN KEY ("datasetId") REFERENCES public."UserDataset"(id) ON UPDATE CASCADE ON DELETE SET NULL;


--
-- Name: Recipe Recipe_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Recipe"
    ADD CONSTRAINT "Recipe_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: Session Session_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."Session"
    ADD CONSTRAINT "Session_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: UserAIConnection UserAIConnection_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."UserAIConnection"
    ADD CONSTRAINT "UserAIConnection_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: UserDatabaseConnection UserDatabaseConnection_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."UserDatabaseConnection"
    ADD CONSTRAINT "UserDatabaseConnection_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: UserDataset UserDataset_sourceConnectionId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."UserDataset"
    ADD CONSTRAINT "UserDataset_sourceConnectionId_fkey" FOREIGN KEY ("sourceConnectionId") REFERENCES public."UserDatabaseConnection"("connectionId") ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: UserDataset UserDataset_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."UserDataset"
    ADD CONSTRAINT "UserDataset_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: VerificationToken VerificationToken_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VerificationToken"
    ADD CONSTRAINT "VerificationToken_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: VirtualDatasetChat VirtualDatasetChat_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VirtualDatasetChat"
    ADD CONSTRAINT "VirtualDatasetChat_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: VisualizationInstance VisualizationInstance_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."VisualizationInstance"
    ADD CONSTRAINT "VisualizationInstance_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- Name: user_audio_presets user_audio_presets_userId_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_audio_presets
    ADD CONSTRAINT "user_audio_presets_userId_fkey" FOREIGN KEY ("userId") REFERENCES public."User"(id) ON UPDATE CASCADE ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict Gebf7FpDRTD3PY8ANfOChDaTQrIFwjert3JDJu3CbBjJKynL81puAbRu4UhuSto

