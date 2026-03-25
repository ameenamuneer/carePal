import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';
import 'package:permission_handler/permission_handler.dart';
import '../services/api_service.dart';

class WebAgentScreen extends StatefulWidget {
  const WebAgentScreen({super.key});

  @override
  State<WebAgentScreen> createState() => _WebAgentScreenState();
}

class _WebAgentScreenState extends State<WebAgentScreen> {
  WebViewController? _controller;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _initWebView();
  }

  Future<void> _initWebView() async {
    // Request permissions for camera and mic which the HTML uses
    await [
      Permission.camera,
      Permission.microphone,
    ].request();

    late final PlatformWebViewControllerCreationParams params;
    if (WebViewPlatform.instance is AndroidWebViewPlatform) {
      params = AndroidWebViewControllerCreationParams();
    } else {
      params = const PlatformWebViewControllerCreationParams();
    }

    final WebViewController controller =
        WebViewController.fromPlatformCreationParams(params);

    await controller.setJavaScriptMode(JavaScriptMode.unrestricted);
    await controller.setBackgroundColor(const Color(0x00000000));
    await controller.setNavigationDelegate(
      NavigationDelegate(
        onPageFinished: (String url) async {
          final token = await ApiService().getAccessToken();
          final baseUrl = ApiService.baseUrl;
          final wsUrl = baseUrl.replaceFirst('https://', 'wss://').replaceFirst('http://', 'ws://');
          
          if (token != null) {
            await controller.runJavaScript("window.startSession('$token', '$wsUrl');");
          }
          if (mounted) {
            setState(() {
              _isLoading = false;
            });
          }
        },
      ),
    );

    if (controller.platform is AndroidWebViewController) {
      AndroidWebViewController.enableDebugging(true);
      (controller.platform as AndroidWebViewController)
          .setMediaPlaybackRequiresUserGesture(false);
      
      // Auto-grant permissions for WebView from the app
      (controller.platform as AndroidWebViewController)
          .setOnPlatformPermissionRequest((PlatformWebViewPermissionRequest request) {
        request.grant();
      });
    }

    try {
      await controller.loadFlutterAsset('assets/html/test_live_api.html');
    } catch (e) {
      // Fallback: try loading as string if asset loading fails
      var htmlString = await rootBundle.loadString('assets/html/test_live_api.html');
      await controller.loadHtmlString(htmlString);
    }

    if (mounted) {
      setState(() {
        _controller = controller;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black, // Dark background to feel seamless if it's borderless
      body: SafeArea(
        child: Stack(
          children: [
            if (_controller != null) WebViewWidget(controller: _controller!),
            if (_isLoading)
              const Center(
                child: CircularProgressIndicator(),
              ),
            // Back button overlaid on top
            Positioned(
              top: 16,
              left: 16,
              child: IconButton(
                icon: const Icon(Icons.arrow_back, color: Colors.blueAccent),
                onPressed: () => Navigator.of(context).pop(),
                style: IconButton.styleFrom(
                  backgroundColor: Colors.white.withOpacity(0.5),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
