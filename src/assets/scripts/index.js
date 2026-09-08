//import { marked } from 'marked';
import '../styles/main.css';
import '../styles/allauth_styles.css';
import './login.js'
//import mermaid from 'mermaid';

import Alpine from 'alpinejs';

window.Alpine = Alpine;
Alpine.start();

window.htmx = require('htmx.org');

window.addEventListener('load', () => {
    document.getElementById('message').textContent = 'Welcome to the {{ project_name }} application!';
    console.log('Hello, {{ project_name }}!'); 
});
