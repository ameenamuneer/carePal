import 'package:flutter/material.dart';
import '../core/app_colors.dart';
import 'dart:math' as math;

class CarePalLogo extends StatelessWidget {
  final double size;
  final bool showText;
  final Color? color;

  const CarePalLogo({
    super.key,
    this.size = 120,
    this.showText = true,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final logoColor = color ?? AppColors.primary;

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        CustomPaint(
          size: Size(size, size),
          painter: _LogoPainter(color: logoColor),
        ),
        if (showText) ...[
          SizedBox(width: size * 0.15),
          RichText(
            text: TextSpan(
              style: TextStyle(
                fontSize: size * 0.3,
                fontWeight: FontWeight.bold,
                letterSpacing: -0.5,
              ),
              children: [
                TextSpan(
                  text: 'Care',
                  style: TextStyle(color: AppColors.primaryDark),
                ),
                TextSpan(
                  text: 'PAL',
                  style: TextStyle(color: AppColors.primary),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _LogoPainter extends CustomPainter {
  final Color color;

  _LogoPainter({required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final centerX = size.width / 2;
    final centerY = size.height / 2;
    final radius = size.width * 0.45;

    // 1. Outer Circular Pulse (dashed circle)
    final outerCirclePaint = Paint()
      ..color = color.withOpacity(0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;

    _drawDashedCircle(
      canvas,
      Offset(centerX, centerY),
      radius,
      outerCirclePaint,
      dashWidth: 6,
      dashSpace: 4,
    );

    // 2. Heart Shape Background
    final heartPath = _createHeartPath(size);
    final heartPaint = Paint()
      ..color = color.withOpacity(0.1)
      ..style = PaintingStyle.fill;

    canvas.drawPath(heartPath, heartPaint);

    // 3. Dynamic Pulse Line (ECG-like)
    final pulsePath = _createPulsePath(size);
    final pulsePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    canvas.drawPath(pulsePath, pulsePaint);

    // 4. AI Pulse Glow (orange dot)
    final glowPaint = Paint()
      ..color = AppColors.alert
      ..style = PaintingStyle.fill;

    canvas.drawCircle(
      Offset(centerX, centerY + size.height * 0.2),
      4,
      glowPaint,
    );

    // Optional: Add glow effect
    final glowOuterPaint = Paint()
      ..color = AppColors.alert.withOpacity(0.3)
      ..style = PaintingStyle.fill;

    canvas.drawCircle(
      Offset(centerX, centerY + size.height * 0.2),
      8,
      glowOuterPaint,
    );
  }

  void _drawDashedCircle(
    Canvas canvas,
    Offset center,
    double radius,
    Paint paint, {
    required double dashWidth,
    required double dashSpace,
  }) {
    final path = Path();
    double startAngle = 0;
    const totalAngle = 2 * 3.14159; // 360 degrees in radians
    final dashCount = (totalAngle * radius) / (dashWidth + dashSpace);

    for (int i = 0; i < dashCount; i++) {
      final angle1 = startAngle + (i * (dashWidth + dashSpace)) / radius;
      final angle2 = angle1 + dashWidth / radius;

      final x1 = center.dx + radius * math.cos(angle1);
      final y1 = center.dy + radius * math.sin(angle1);
      final x2 = center.dx + radius * math.cos(angle2);
      final y2 = center.dy + radius * math.sin(angle2);

      path.moveTo(x1, y1);
      path.arcToPoint(Offset(x2, y2), radius: Radius.circular(radius));
    }

    canvas.drawPath(path, paint);
  }

  Path _createHeartPath(Size size) {
    final path = Path();
    final centerX = size.width / 2;
    final scale = size.width / 100;

    // Simplified heart shape
    path.moveTo(centerX, 85 * scale);

    // Left side of heart
    path.cubicTo(
      15 * scale,
      60 * scale,
      15 * scale,
      38 * scale,
      15 * scale,
      38 * scale,
    );
    path.cubicTo(
      15 * scale,
      25 * scale,
      25 * scale,
      15 * scale,
      38 * scale,
      15 * scale,
    );
    path.cubicTo(
      44 * scale,
      15 * scale,
      48 * scale,
      18 * scale,
      centerX,
      22 * scale,
    );

    // Right side of heart
    path.cubicTo(
      52 * scale,
      18 * scale,
      56 * scale,
      15 * scale,
      62 * scale,
      15 * scale,
    );
    path.cubicTo(
      75 * scale,
      15 * scale,
      85 * scale,
      25 * scale,
      85 * scale,
      38 * scale,
    );
    path.cubicTo(
      85 * scale,
      60 * scale,
      centerX,
      85 * scale,
      centerX,
      85 * scale,
    );

    path.close();
    return path;
  }

  Path _createPulsePath(Size size) {
    final path = Path();
    final scale = size.width / 100;

    // ECG-like pulse line
    path.moveTo(25 * scale, 50 * scale);
    path.lineTo(35 * scale, 50 * scale);
    path.lineTo(42 * scale, 30 * scale); // Up spike
    path.lineTo(52 * scale, 70 * scale); // Down spike
    path.lineTo(60 * scale, 45 * scale); // Up again
    path.lineTo(65 * scale, 50 * scale);
    path.lineTo(75 * scale, 50 * scale);

    return path;
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
