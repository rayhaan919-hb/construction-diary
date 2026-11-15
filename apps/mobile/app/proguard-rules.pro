# Keep kotlinx.serialization DTOs and Room/Hilt metadata
-keepattributes *Annotation*, InnerClasses, Signature, Exceptions
-dontnote kotlinx.serialization.SerializationKt
-keep,includedescriptorclasses class com.sitediary.mobile.data.remote.dto.**$$serializer { *; }
-keepclassmembers class com.sitediary.mobile.data.remote.dto.** {
    *** Companion;
}

# Retrofit / OkHttp
-keepattributes RuntimeVisibleAnnotations,RuntimeVisibleParameterAnnotations
-keepclassmembers,allowshrinking,allowobfuscation interface * {
    @retrofit2.http.* <methods>;
}
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn retrofit2.**

# Room & Hilt
-keep class * extends androidx.room.RoomDatabase
-dontwarn androidx.room.**

# Firebase Messaging (optional when google-services.json is absent)
-dontwarn com.google.firebase.**
-dontwarn com.google.android.gms.**
-keepclassmembers class * extends com.google.firebase.messaging.FirebaseMessagingService {
    <init>();
}
