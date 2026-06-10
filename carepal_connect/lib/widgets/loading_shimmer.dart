import 'package:flutter/material.dart';

class LoadingShimmer extends StatefulWidget {
  final double height;
  final double width;
  final double borderRadius;

  const LoadingShimmer({
    super.key,
    this.height = 100,
    this.width = double.infinity,
    this.borderRadius = 16,
  });

  @override
  State<LoadingShimmer> createState() => _LoadingShimmerState();
}

class _LoadingShimmerState extends State<LoadingShimmer>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<Color?> _colorAnimation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: const Duration(milliseconds: 1500),
      vsync: this,
    )..repeat(reverse: true);

    _colorAnimation = ColorTween(
      begin: Colors.grey[200],
      end: Colors.grey[100],
    ).animate(_controller);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _colorAnimation,
      builder: (context, child) {
        return Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            color: _colorAnimation.value,
            borderRadius: BorderRadius.circular(widget.borderRadius),
          ),
        );
      },
    );
  }
}

class PatientCardShimmer extends StatelessWidget {
  const PatientCardShimmer({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.grey.withOpacity(0.1)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const LoadingShimmer(width: 48, height: 48, borderRadius: 24),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: const [
                    LoadingShimmer(height: 16, borderRadius: 4),
                    SizedBox(height: 8),
                    LoadingShimmer(width: 80, height: 12, borderRadius: 4),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          const LoadingShimmer(height: 40, borderRadius: 10),
        ],
      ),
    );
  }
}
