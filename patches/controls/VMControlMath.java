package com.norwood.mcheli.vm;

public final class VMControlMath {
    public static double clamp(double value, double min, double max) {
        return Double.isFinite(value) ? Math.max(min, Math.min(max, value)) : min;
    }
    public static double axis(double raw, double low, double center, double high, boolean inverted, double deadzone, double expo) {
        if (!Double.isFinite(raw + low + center + high) || center - low < 0.08 || high - center < 0.08) return 0;
        double x = clamp((raw - center) / (raw >= center ? high - center : center - low), -1, 1);
        double dz = clamp(deadzone, 0, 0.3);
        x = Math.abs(x) <= dz ? 0 : Math.copySign((Math.abs(x) - dz) / (1 - dz), x);
        double e = clamp(expo, 0, 0.85);
        x = x * (1 - e) + x * x * x * e;
        return inverted ? -x : x;
    }
    public static double throttle(double raw, double low, double high, boolean inverted) {
        if (!Double.isFinite(raw + low + high) || high - low < 0.16) return 0;
        double t = clamp((raw - low) / (high - low), 0, 1);
        return inverted ? 1 - t : t;
    }
    public static double smooth(double previous, double target, double dt, double seconds) {
        return previous + (target - previous) * (1 - Math.exp(-clamp(dt, 0, 0.1) / Math.max(0.001, seconds)));
    }
    public static double angle(double current, double target, double dt, double rate) {
        double difference = (target - current) % 360;
        if (difference > 180) difference -= 360;
        if (difference < -180) difference += 360;
        return current + clamp(difference * 5, -rate, rate) * clamp(dt, 0, 0.05);
    }
    public static float[] euler(double x,double y,double z,double w) {
        double norm=Math.sqrt(x*x+y*y+z*z+w*w);
        if(!Double.isFinite(norm)||norm<1e-12)return new float[]{0,0,0};
        x/=norm;y/=norm;z/=norm;w/=norm;
        double m00=1-2*y*y-2*z*z,m01=2*x*y-2*w*z,m02=2*z*x+2*w*y;
        double m11=1-2*z*z-2*x*x,m20=2*z*x-2*w*y,m21=2*y*z+2*w*x,m22=1-2*x*x-2*y*y;
        double b=-Math.asin(clamp(m21,-1,1)),cos=Math.cos(b),a,c;
        if(Math.abs(cos)>=1e-5){c=Math.atan2(m20,m22);a=Math.asin(clamp(m01/cos,-1,1));}
        else{c=Math.atan2(-m02,m00);a=0;}
        a=Math.toDegrees(a);if(m11<0)a=180-a;
        return new float[]{(float)-Math.toDegrees(b),(float)-Math.toDegrees(c),(float)-a};
    }
}
