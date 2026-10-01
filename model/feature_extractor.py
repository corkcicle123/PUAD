import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
from torchvision.models import ResNet18_Weights

class ResNet18FeatureExtractor(nn.Module):
    """
    PatchCore feature extractor using ResNet-18.
    Extracts features from layer2 and layer3, aggregates neighborhood context
    via local average pooling, and concatenates them.
    """
    def __init__(self, device='cpu'):
        super().__init__()
        self.device = device
        
        # Load pretrained ResNet-18
        weights = ResNet18_Weights.IMAGENET1K_V1
        backbone = models.resnet18(weights=weights)
        
        # Extract initial layers up to layer3
        self.conv1 = backbone.conv1
        self.bn1 = backbone.bn1
        self.relu = backbone.relu
        self.maxpool = backbone.maxpool
        self.layer1 = backbone.layer1
        self.layer2 = backbone.layer2
        self.layer3 = backbone.layer3
        
        # Freeze backbone parameters
        for param in self.parameters():
            param.requires_grad = False
            
        self.eval()
        self.to(self.device)
        
        # Neighborhood aggregation pooler
        self.avg_pool = nn.AvgPool2d(kernel_size=3, stride=1, padding=1)

    def forward(self, x):
        """
        x: Tensor of shape (B, 3, H, W), normalized ImageNet range
        returns: patch_embeddings of shape (B, H_patch * W_patch, D)
                 and spatial resolution (H_patch, W_patch)
        """
        with torch.no_grad():
            x = x.to(self.device)
            x0 = self.relu(self.bn1(self.conv1(x)))
            x0 = self.maxpool(x0)
            x1 = self.layer1(x0)
            x2 = self.layer2(x1)  # Shape: (B, 128, H/8, W/8) -> e.g. (B, 128, 28, 28)
            x3 = self.layer3(x2)  # Shape: (B, 256, H/16, W/16) -> e.g. (B, 256, 14, 14)
            
            # Upsample layer3 to layer2 resolution
            x3_upsampled = F.interpolate(
                x3, size=x2.shape[-2:], mode='bilinear', align_corners=False
            )
            
            # Apply local neighborhood pooling to capture context around each patch
            p2 = self.avg_pool(x2)
            p3 = self.avg_pool(x3_upsampled)
            
            # Concatenate along channel dimension: 128 + 256 = 384
            patch_features = torch.cat([p2, p3], dim=1) # (B, 384, H2, W2)
            
            B, C, H_patch, W_patch = patch_features.shape
            
            # Reshape to (B, H_patch * W_patch, C)
            patch_embeddings = patch_features.permute(0, 2, 3, 1).reshape(B, H_patch * W_patch, C)
            
            # L2-normalize patch vectors along channel dimension onto unit hypersphere
            patch_embeddings = F.normalize(patch_embeddings, p=2, dim=-1)
            
            return patch_embeddings, (H_patch, W_patch)
