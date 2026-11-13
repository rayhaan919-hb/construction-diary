# Keep kotlinx.serialization DTOs and Room/Hilt metadata
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.SerializationKt
-keep,includedescriptorclasses class com.sitediary.mobile.data.remote.dto.**$$serializer { *; }
-keepclassmembers class com.sitediary.mobile.data.remote.dto.** {
    *** Companion;
}
