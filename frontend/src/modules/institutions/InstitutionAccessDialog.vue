<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElInput,
  ElMessage,
  ElOption,
  ElSelect,
  ElTabPane,
  ElTabs,
  ElTag,
} from "element-plus";
import { usePrioritizationStore } from "../../stores/usePrioritizationStore";
import { useI18n } from "../../i18n/useI18n";

const props = defineProps<{ visible: boolean }>();
const emit = defineEmits<{ (event: "update:visible", value: boolean): void }>();
const store = usePrioritizationStore();
const { locale } = useI18n();
const isSpanish = computed(() => locale.value === "es");
const isSubmitting = ref(false);
const activeTab = ref("login");
const registrationResult = ref<{ registration_code: string; message: string } | null>(null);
const inviteResult = ref<{ invite_code: string; expires_at: string } | null>(null);
const formError = ref("");

const loginForm = reactive({ email: "", password: "" });
const registrationForm = reactive({
  name: "",
  country: "El Salvador",
  sector: "",
  contact_name: "",
  email: "",
  password: "",
});
const joinForm = reactive({ invite_code: "", display_name: "", email: "", password: "" });

const account = computed(() => store.institutionSession?.account ?? null);
const isLoggedIn = computed(() => Boolean(store.institutionSession));
const isVerified = computed(() => store.hasVerifiedInstitution);
const copy = computed(() => isSpanish.value ? {
  title: "Acceso institucional",
  subtitle: "Coordinación pública con autoría individual y organizaciones verificadas.",
  login: "Iniciar sesión",
  register: "Registrar organización",
  join: "Unirme con invitación",
  email: "Correo institucional",
  password: "Contraseña (mínimo 12 caracteres)",
  name: "Nombre de la institución",
  country: "País",
  sector: "Tipo de organización",
  contactName: "Tu nombre y apellido",
  inviteCode: "Código de invitación",
  signIn: "Entrar",
  submitRegistration: "Enviar solicitud",
  joinAction: "Crear mi cuenta",
  close: "Cerrar",
  logout: "Cerrar sesión",
  pending: "En revisión",
  refreshStatus: "Revisar estado",
  verified: "Institución verificada",
  rejected: "Solicitud rechazada",
  requestCode: "Código de seguimiento",
  codeNotice: "Este código solo identifica la solicitud; no demuestra que la organización sea auténtica. La revisión debe comprobarla por canales oficiales.",
  requestSent: "Solicitud enviada",
  pendingBody: "Podrás iniciar sesión, pero no publicar acciones institucionales hasta que el equipo de FirstSpot verifique la organización.",
  invite: "Crear invitación de un solo uso",
  inviteCreated: "Código de invitación (se muestra una sola vez)",
  inviteCopy: "Copiar código",
  noSensitive: "No incluyas datos personales de pacientes o personas afectadas.",
  sectors: ["Protección civil", "Policía", "Bomberos", "Salud", "ONG / ayuda humanitaria", "Gobierno local", "Otro"],
  error: "No se pudo completar la solicitud",
} : {
  title: "Institutional access",
  subtitle: "Public coordination with individual attribution and verified organizations.",
  login: "Sign in",
  register: "Register organization",
  join: "Join with invitation",
  email: "Institutional email",
  password: "Password (at least 12 characters)",
  name: "Organization name",
  country: "Country",
  sector: "Organization type",
  contactName: "Your full name",
  inviteCode: "Invitation code",
  signIn: "Sign in",
  submitRegistration: "Submit request",
  joinAction: "Create my account",
  close: "Close",
  logout: "Sign out",
  pending: "Under review",
  refreshStatus: "Refresh status",
  verified: "Verified organization",
  rejected: "Request rejected",
  requestCode: "Tracking code",
  codeNotice: "This code only identifies the request; it does not prove the organization is authentic. Review must verify it through official channels.",
  requestSent: "Request submitted",
  pendingBody: "You can sign in, but cannot publish institutional actions until FirstSpot independently verifies the organization.",
  invite: "Create one-time invitation",
  inviteCreated: "Invitation code (shown only once)",
  inviteCopy: "Copy code",
  noSensitive: "Do not include personal data about patients or affected people.",
  sectors: ["Civil protection", "Police", "Fire service", "Healthcare", "NGO / humanitarian aid", "Local government", "Other"],
  error: "The request could not be completed",
});

watch(() => props.visible, (visible) => {
  if (!visible) return;
  formError.value = "";
  if (isLoggedIn.value) activeTab.value = "account";
  else if (activeTab.value === "account") activeTab.value = "login";
});

watch(isLoggedIn, (loggedIn) => {
  if (loggedIn) activeTab.value = "account";
});

async function submitLogin(): Promise<void> {
  await run(async () => {
    await store.loginInstitution(loginForm);
    ElMessage.success(isSpanish.value ? "Sesión iniciada" : "Signed in");
  });
}

async function submitRegistration(): Promise<void> {
  await run(async () => {
    registrationResult.value = await store.registerInstitution(registrationForm);
  });
}

async function submitJoin(): Promise<void> {
  await run(async () => {
    await store.joinInstitution(joinForm);
    ElMessage.success(isSpanish.value ? "Ya formas parte de la organización" : "You joined the organization");
  });
}

async function createInvite(): Promise<void> {
  await run(async () => {
    inviteResult.value = await store.createInstitutionInvite();
  });
}

async function run(action: () => Promise<void>): Promise<void> {
  formError.value = "";
  isSubmitting.value = true;
  try {
    await action();
  } catch (error) {
    formError.value = error instanceof Error ? error.message : copy.value.error;
  } finally {
    isSubmitting.value = false;
  }
}

async function copyInvite(): Promise<void> {
  if (!inviteResult.value) return;
  try {
    await navigator.clipboard.writeText(inviteResult.value.invite_code);
    ElMessage.success(isSpanish.value ? "Código copiado" : "Code copied");
  } catch {
    formError.value = isSpanish.value ? "No se pudo copiar; selecciona el código manualmente." : "Could not copy; select the code manually.";
  }
}
</script>

<template>
  <ElDialog
    :model-value="props.visible"
    :title="copy.title"
    width="min(590px, calc(100vw - 28px))"
    append-to-body
    :close-on-click-modal="false"
    class="institution-access-dialog"
    @update:model-value="(value) => emit('update:visible', Boolean(value))"
  >
    <p class="dialog-intro">{{ copy.subtitle }}</p>
    <ElAlert v-if="formError" :title="formError" type="error" show-icon :closable="false" />

    <section v-if="isLoggedIn && account" class="account-panel">
      <div class="account-heading">
        <div class="account-avatar">{{ account.institution.name.slice(0, 1).toUpperCase() }}</div>
        <div class="account-heading-copy">
          <strong>{{ account.institution.name }}</strong>
          <span>{{ account.display_name }} · {{ account.email }}</span>
        </div>
        <ElTag :type="isVerified ? 'success' : account.institution.verification_status === 'rejected' ? 'danger' : 'warning'" effect="plain">
          {{ isVerified ? copy.verified : account.institution.verification_status === 'rejected' ? copy.rejected : copy.pending }}
        </ElTag>
      </div>
      <ElAlert
        v-if="!isVerified"
        :title="copy.pendingBody"
        :description="`${copy.requestCode}: ${account.institution.registration_code}`"
        type="warning"
        show-icon
        :closable="false"
      />
      <ElButton v-if="!isVerified" text type="primary" :loading="isSubmitting" @click="run(() => store.restoreInstitutionSession())">{{ copy.refreshStatus }}</ElButton>
      <div v-else class="invite-tools">
        <ElButton type="primary" :loading="isSubmitting" @click="createInvite">{{ copy.invite }}</ElButton>
        <div v-if="inviteResult" class="invite-result">
          <label>{{ copy.inviteCreated }}</label>
          <code>{{ inviteResult.invite_code }}</code>
          <ElButton size="small" @click="copyInvite">{{ copy.inviteCopy }}</ElButton>
          <small>{{ new Date(inviteResult.expires_at).toLocaleString() }}</small>
        </div>
      </div>
      <div class="account-actions">
        <span>{{ account.role === 'owner' ? (isSpanish ? 'Administradora de la organización' : 'Organization owner') : (isSpanish ? 'Miembro de la organización' : 'Organization member') }}</span>
        <ElButton text type="danger" @click="store.logoutInstitution()">{{ copy.logout }}</ElButton>
      </div>
    </section>

    <template v-else-if="registrationResult">
      <div class="registration-result">
        <div class="success-mark">✓</div>
        <h3>{{ copy.requestSent }}</h3>
        <p>{{ registrationResult.message }}</p>
        <span>{{ copy.requestCode }}</span>
        <code>{{ registrationResult.registration_code }}</code>
        <ElAlert :title="copy.codeNotice" type="warning" show-icon :closable="false" />
        <ElButton type="primary" @click="registrationResult = null; activeTab = 'login'">{{ copy.close }}</ElButton>
      </div>
    </template>

    <ElTabs v-else v-model="activeTab" class="access-tabs">
      <ElTabPane :label="copy.login" name="login">
        <form class="access-form" @submit.prevent="submitLogin">
          <label>{{ copy.email }}<ElInput v-model="loginForm.email" type="email" autocomplete="username" required /></label>
          <label>{{ copy.password }}<ElInput v-model="loginForm.password" type="password" autocomplete="current-password" show-password required /></label>
          <ElButton native-type="submit" type="primary" :loading="isSubmitting" class="submit-button">{{ copy.signIn }}</ElButton>
        </form>
      </ElTabPane>

      <ElTabPane :label="copy.register" name="register">
        <form class="access-form two-column-form" @submit.prevent="submitRegistration">
          <label class="wide-field">{{ copy.name }}<ElInput v-model="registrationForm.name" minlength="2" maxlength="160" required /></label>
          <label>{{ copy.country }}<ElInput v-model="registrationForm.country" maxlength="80" required /></label>
          <label>{{ copy.sector }}
            <ElSelect v-model="registrationForm.sector" allow-create filterable default-first-option required>
              <ElOption v-for="sector in copy.sectors" :key="sector" :label="sector" :value="sector" />
            </ElSelect>
          </label>
          <label>{{ copy.contactName }}<ElInput v-model="registrationForm.contact_name" maxlength="100" autocomplete="name" required /></label>
          <label>{{ copy.email }}<ElInput v-model="registrationForm.email" type="email" maxlength="254" autocomplete="email" required /></label>
          <label class="wide-field">{{ copy.password }}<ElInput v-model="registrationForm.password" type="password" minlength="12" maxlength="128" autocomplete="new-password" show-password required /></label>
          <ElButton native-type="submit" type="primary" :loading="isSubmitting" class="submit-button wide-field">{{ copy.submitRegistration }}</ElButton>
        </form>
      </ElTabPane>

      <ElTabPane :label="copy.join" name="join">
        <form class="access-form" @submit.prevent="submitJoin">
          <label>{{ copy.inviteCode }}<ElInput v-model="joinForm.invite_code" autocomplete="off" required /></label>
          <label>{{ copy.contactName }}<ElInput v-model="joinForm.display_name" autocomplete="name" required /></label>
          <label>{{ copy.email }}<ElInput v-model="joinForm.email" type="email" autocomplete="email" required /></label>
          <label>{{ copy.password }}<ElInput v-model="joinForm.password" type="password" minlength="12" maxlength="128" autocomplete="new-password" show-password required /></label>
          <ElButton native-type="submit" type="primary" :loading="isSubmitting" class="submit-button">{{ copy.joinAction }}</ElButton>
        </form>
      </ElTabPane>
    </ElTabs>

    <p v-if="!isLoggedIn && !registrationResult" class="privacy-note">{{ copy.noSensitive }}</p>
  </ElDialog>
</template>

<style scoped>
.dialog-intro { margin: -4px 0 18px; color: #637184; font-size: 13px; line-height: 1.5; }
.access-tabs { min-height: 300px; }
.access-form { display: grid; gap: 14px; padding: 14px 2px 4px; }
.access-form label { display: grid; gap: 6px; color: #465468; font-size: 12px; font-weight: 650; }
.two-column-form { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.wide-field { grid-column: 1 / -1; }
.submit-button { justify-self: end; min-width: 150px; }
.privacy-note { margin: 12px 0 0; padding-top: 12px; border-top: 1px solid #e0e6ed; color: #7b8795; font-size: 11px; }
.account-panel { display: grid; gap: 18px; }
.account-heading { display: flex; align-items: center; gap: 12px; padding: 14px; background: #f2f5f8; border: 1px solid #d9e0e8; border-radius: 5px; }
.account-avatar { width: 38px; height: 38px; display: grid; place-items: center; border-radius: 4px; color: white; background: #168e81; font-weight: 700; }
.account-heading-copy { display: grid; gap: 3px; flex: 1; min-width: 0; }
.account-heading-copy strong { color: #273244; font-size: 14px; }
.account-heading-copy span { color: #687789; font-size: 11px; overflow-wrap: anywhere; }
.account-actions { display: flex; align-items: center; justify-content: space-between; border-top: 1px solid #e0e6ed; padding-top: 12px; color: #687789; font-size: 12px; }
.invite-tools { display: grid; justify-items: start; gap: 12px; }
.invite-result { display: grid; gap: 8px; width: 100%; padding: 12px; border: 1px solid #c8d8e4; background: #f8fafc; border-radius: 4px; }
.invite-result label, .registration-result > span { color: #657487; font-size: 11px; font-weight: 700; text-transform: uppercase; }
.invite-result code, .registration-result code { width: fit-content; padding: 8px 10px; background: #edf2f7; border: 1px solid #d4dde6; color: #263447; font-size: 14px; overflow-wrap: anywhere; }
.invite-result small { color: #778494; }
.registration-result { display: grid; justify-items: center; gap: 12px; padding: 8px 0 12px; text-align: center; }
.registration-result h3 { margin: 0; color: #253143; }
.registration-result p { margin: 0; color: #637184; font-size: 13px; line-height: 1.5; }
.success-mark { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 50%; color: #fff; background: #168e81; font-size: 23px; }
.registration-result :deep(.el-alert) { text-align: left; }
:global(.dark) .dialog-intro, :global(.dark) .access-form label, :global(.dark) .account-actions { color: #aab6c4; }
:global(.dark) .account-heading, :global(.dark) .invite-result { background: #232a33; border-color: #3c4652; }
:global(.dark) .account-heading-copy strong, :global(.dark) .registration-result h3 { color: #e5eaf0; }
:global(.dark) .account-heading-copy span, :global(.dark) .registration-result p { color: #aab6c4; }
:global(.dark) .invite-result code, :global(.dark) .registration-result code { color: #e1e7ee; background: #171c22; border-color: #3c4652; }
:global(.dark) .privacy-note, :global(.dark) .account-actions { border-color: #3c4652; }
@media (max-width: 540px) { .two-column-form { grid-template-columns: 1fr; } .wide-field { grid-column: auto; } .account-heading { flex-wrap: wrap; } .account-heading-copy { min-width: calc(100% - 64px); } }
</style>
