import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import ArcoVue from '@arco-design/web-vue';
import '@arco-design/web-vue/dist/arco.css';
import { createPinia } from 'pinia'
import router from './router'
import i18n from './i18n';

const app = createApp(App);
const pinia = createPinia();

app.use(ArcoVue);
app.use(pinia);
app.use(router);
app.use(i18n);
app.mount('#app');
