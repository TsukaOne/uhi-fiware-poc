<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
    xmlns="http://www.opengis.net/sld"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink">
  <NamedLayer>
    <Name>ndwi</Name>
    <UserStyle>
      <Name>ndwi_style</Name>
      <Title>Normalized Difference Water Index - Brussels</Title>
      <FeatureTypeStyle>
        <Rule>
          <RasterSymbolizer>
            <ColorMap>
              <ColorMapEntry color="#8c510a" quantity="0"   opacity="1"/>
              <ColorMapEntry color="#bf812d" quantity="33"  opacity="1"/>
              <ColorMapEntry color="#dfc27d" quantity="66"  opacity="1"/>
              <ColorMapEntry color="#f6e8c3" quantity="90"  opacity="1"/>
              <ColorMapEntry color="#ffffff" quantity="127" opacity="1"/>
              <ColorMapEntry color="#c7eae5" quantity="150" opacity="1"/>
              <ColorMapEntry color="#80cdc1" quantity="170" opacity="1"/>
              <ColorMapEntry color="#35978f" quantity="191" opacity="1"/>
              <ColorMapEntry color="#01665e" quantity="220" opacity="1"/>
              <ColorMapEntry color="#003c30" quantity="254" opacity="1"/>
            </ColorMap>
          </RasterSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
