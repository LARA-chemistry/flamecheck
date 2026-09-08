# web development

A very nice Blog post about setting up Webpack with Django can be found here: [Setting up Webpack with Django](https://bugbytes.io/posts/django-and-webpack-external-libraries-loaders-and-stylesheets/)

## Troubleshooting Webpack Development

When working with Webpack in a Django project, you might encounter issues related to the development server or asset compilation. Here are some common troubleshooting steps:

1. **Check Webpack Configuration**: Ensure that your `webpack.config.js` is correctly set up for development. Look for the `devServer` configuration and ensure it matches your Django settings.

2. **Run Webpack in Development Mode**: Make sure you are running Webpack in development mode. You can do this by using the command:
   ```bash
   npm run dev
   ```
   or
   ```bash
   yarn dev
   ```

3. **Clear Cache**: Sometimes, Webpack might serve cached files. Clear the cache by running:
   ```bash
    npm run clean
    ```

4. **Check for Errors in the Console**: Open your browser's developer console and check for any JavaScript errors that might indicate issues with your Webpack setup.



## Checking generated CSS files

To verify that your CSS files are being generated correctly, you can check the contents of the CSS files

by running the following command in your terminal:

```bash
    head -20 src/todo_pro2/static/css/todo_pro2_base.css
```

This should indicate that Tailwind 4 CSS is being generated correctly. If you see the expected Tailwind CSS classes, then your setup is working as intended.

