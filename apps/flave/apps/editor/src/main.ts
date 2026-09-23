import { mount } from 'svelte';
import './styles/theme.css';
import './styles/app.css';
import App from './App.svelte';

const target = document.getElementById('app');
if (!target) throw new Error('no #app');

export default mount(App, { target });
