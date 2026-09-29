<?php
/**
 * Plugin Name: FinkiBOT Chat Widget
 * Description: Adds the FinkiBOT floating chat bubble to every page of the site.
 * Version: 1.0.0
 * Author: FinkiBOT
 *
 * What this does, and what it deliberately does NOT do:
 * - It only loads one small, dependency-free JavaScript file (finkibot-widget.js) on
 *   the public-facing site via wp_enqueue_script. That script injects a floating
 *   bubble button and, when clicked, an <iframe> pointing at FinkiBOT's own "/widget"
 *   page (see frontend/src/routes/widget.tsx in the FinkiBOT repo).
 * - It does NOT talk to WordPress's own REST API, database, or content in any way,
 *   and does NOT need any FinkiBOT backend changes (no CORS setup) — the chat runs
 *   entirely inside that iframe, on FinkiBOT's own origin, exactly as if a visitor had
 *   opened FinkiBOT's site directly in a new tab.
 * - The only thing an admin configures is *which* FinkiBOT deployment to point at
 *   (Settings → FinkiBOT Widget), since that URL differs between local development
 *   and the real production deployment.
 */

if (!defined('ABSPATH')) {
    exit; // No direct access.
}

define('FINKIBOT_WIDGET_VERSION', '1.0.0');
define('FINKIBOT_WIDGET_OPTION', 'finkibot_widget_url');

/**
 * Enqueues the widget script on every front-end page (not wp-admin), pointing it at
 * the configured FinkiBOT URL via a data attribute the script itself reads.
 */
function finkibot_widget_enqueue_script() {
    if (is_admin()) {
        return;
    }

    $finkibot_url = get_option(FINKIBOT_WIDGET_OPTION, '');
    if (empty($finkibot_url)) {
        return; // Not configured yet — nothing to embed.
    }

    wp_enqueue_script(
        'finkibot-widget',
        plugins_url('finkibot-widget.js', __FILE__),
        array(),
        FINKIBOT_WIDGET_VERSION,
        true // load in the footer
    );

    // The script reads this via document.currentScript.dataset.finkibotUrl — this
    // filter is WordPress's supported way to add a plain HTML attribute (not a JS
    // variable) to an already-enqueued <script> tag.
    add_filter('script_loader_tag', function ($tag, $handle) use ($finkibot_url) {
        if ($handle !== 'finkibot-widget') {
            return $tag;
        }
        return str_replace(
            ' src=',
            ' data-finkibot-url="' . esc_url($finkibot_url) . '" src=',
            $tag
        );
    }, 10, 2);
}
add_action('wp_enqueue_scripts', 'finkibot_widget_enqueue_script');

/**
 * A single settings field under Settings → FinkiBOT Widget, so the FinkiBOT URL can be
 * changed (e.g. when moving from a staging deployment to the real production one)
 * without editing any file or redeploying the plugin.
 */
function finkibot_widget_register_settings() {
    register_setting('finkibot_widget', FINKIBOT_WIDGET_OPTION, array(
        'type' => 'string',
        'sanitize_callback' => 'esc_url_raw',
        'default' => '',
    ));

    add_settings_section(
        'finkibot_widget_section',
        'FinkiBOT Widget',
        function () {
            echo '<p>Внесете ја адресата на FinkiBOT инсталацијата (без завршна коса црта), на пр. <code>https://finkibot.example.com</code>.</p>';
        },
        'finkibot-widget'
    );

    add_settings_field(
        FINKIBOT_WIDGET_OPTION,
        'FinkiBOT URL',
        function () {
            $value = get_option(FINKIBOT_WIDGET_OPTION, '');
            printf(
                '<input type="url" name="%s" value="%s" class="regular-text" placeholder="https://finkibot.example.com" />',
                esc_attr(FINKIBOT_WIDGET_OPTION),
                esc_attr($value)
            );
        },
        'finkibot-widget',
        'finkibot_widget_section'
    );
}
add_action('admin_init', 'finkibot_widget_register_settings');

function finkibot_widget_settings_page() {
    ?>
    <div class="wrap">
        <h1>FinkiBOT Widget</h1>
        <form action="options.php" method="post">
            <?php
            settings_fields('finkibot_widget');
            do_settings_sections('finkibot-widget');
            submit_button('Зачувај');
            ?>
        </form>
    </div>
    <?php
}

function finkibot_widget_add_settings_page() {
    add_options_page(
        'FinkiBOT Widget',
        'FinkiBOT Widget',
        'manage_options',
        'finkibot-widget',
        'finkibot_widget_settings_page'
    );
}
add_action('admin_menu', 'finkibot_widget_add_settings_page');